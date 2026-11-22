import json
from contextlib import contextmanager
from decimal import Decimal
from time import perf_counter
from uuid import uuid4

import tiktoken
from langchain_core.callbacks import BaseCallbackHandler
from langsmith import Client, agent_address, trace, tracing_context

from loandesk.core.settings import Settings
from loandesk.domain.contracts import DomainError, utc_now
from loandesk.repositories.document_repository import DocumentRepository, update_record

# USD per million tokens; updated independently of prompt/model architecture versions.
MODEL_PRICES = {
    "gpt-5.6-luna": (Decimal("0.20"), Decimal("0.02"), Decimal("1.20")),
    "gpt-5.4-mini": (Decimal("0.75"), Decimal("0.075"), Decimal("4.50")),
}
PRICE_VERSION = "2026-11-16"


# Estimate provider text charges; reasoning is already included in output_tokens and is not added
# twice.
def estimate_token_cost(
    model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0
) -> float:
    if model not in MODEL_PRICES:
        raise DomainError("Model pricing is not configured; live execution is blocked.")
    if min(input_tokens, output_tokens, cached_tokens) < 0 or cached_tokens > input_tokens:
        raise ValueError("Invalid usage metadata.")
    incoming, cached, outgoing = MODEL_PRICES[model]
    return float(
        (
            (input_tokens - cached_tokens) * incoming
            + cached_tokens * cached
            + output_tokens * outgoing
        )
        / 1000000
    )


class ReviewTelemetry:
    # Associate every model attempt and workflow event with one persisted review.
    def __init__(self, repository: DocumentRepository, review_id: str, settings: Settings):
        self.repository, self.review_id, self.settings = repository, review_id, settings

    # Append a safe lifecycle event atomically; raw document data and credentials never enter
    # events.
    def event(self, name: str, role: str, **details) -> None:
        event = {"id": str(uuid4()), "name": name, "role": role, "at": utc_now(), **details}

        # Apply only this event to the latest record so parallel branches do not overwrite one
        # another.
        def append(record):
            record["events"] = [*record.get("events", []), event]
            return record

        update_record(self.repository, "reviews", self.review_id, append)

    # Wrap a graph node in a local timeline and a LangSmith child span when tracing is enabled.
    @contextmanager
    def step(self, role: str):
        start = perf_counter()
        self.event("agent_started", role)
        try:
            with trace(role, run_type="chain", metadata={"agent_role": role}):
                yield
        except BaseException:
            self.event("agent_failed", role, duration_seconds=round(perf_counter() - start, 6))
            raise
        else:
            self.event("agent_completed", role, duration_seconds=round(perf_counter() - start, 6))

    # Reserve worst-case text cost and a call slot atomically across all concurrent specialist
    # branches.
    def reserve(self, attempt_id: str, input_tokens: int) -> None:
        if input_tokens > 20000:
            raise DomainError(
                "This model context exceeds the low-budget limit. Use shorter evidence files."
            )
        reserved = estimate_token_cost(
            self.settings.model, input_tokens, self.settings.max_output_tokens
        )
        self.repository.insert(
            "budgets", {"id": "development-v1", "version": 1, "reserved_usd": 0.0, "reviews": {}}
        )

        # Keep reservations for unknown/failed calls instead of assuming the provider charged
        # nothing.
        def reserve_budget(budget):
            entries = dict(budget.get("reviews", {}))
            review = dict(entries.get(self.review_id, {"amount": 0.0, "calls": 0, "attempts": {}}))
            if attempt_id in review["attempts"]:
                return budget
            if review["calls"] >= self.settings.max_model_calls_per_review:
                raise DomainError(
                    "The review reached its model-call limit; human review is required."
                )
            if (
                review["amount"] + reserved > self.settings.review_budget_usd
                or budget["reserved_usd"] + reserved > self.settings.session_budget_usd
            ):
                raise DomainError(
                    "The configured model allowance is exhausted. No further model call was made."
                )
            review["calls"] += 1
            review["amount"] += reserved
            review["attempts"][attempt_id] = reserved
            entries[self.review_id] = review
            budget.update(reviews=entries, reserved_usd=budget["reserved_usd"] + reserved)
            return budget

        update_record(self.repository, "budgets", "development-v1", reserve_budget)

    # Reconcile a reservation with known usage; unknown calls remain conservatively reserved.
    def reconcile(self, attempt_id: str, actual_cost: float | None) -> None:
        if actual_cost is None:
            return

        def settle(budget):
            review = budget["reviews"][self.review_id]
            previous = review["attempts"].get(attempt_id)
            if previous is not None:
                adjustment = actual_cost - previous
                review["attempts"][attempt_id] = actual_cost
                review["amount"] += adjustment
                budget["reserved_usd"] += adjustment
            return budget

        update_record(self.repository, "budgets", "development-v1", settle)


class ModelUsageCallback(BaseCallbackHandler):
    raise_error = True
    run_inline = True

    # Keep per-invocation timing and usage separate from LangSmith's aggregate parent spans.
    def __init__(self, telemetry: ReviewTelemetry, role: str):
        self.telemetry, self.role = telemetry, role
        self.attempts: dict[str, float] = {}

    # Count serialized messages plus schema overhead and reserve before the provider is invoked.
    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        attempt = str(run_id)
        payload = json.dumps(
            [[message.model_dump(mode="json") for message in batch] for batch in messages]
        )
        token_count = len(tiktoken.get_encoding("o200k_base").encode(payload)) + 4096
        self.telemetry.reserve(attempt, token_count)
        self.attempts[attempt] = perf_counter()
        self.telemetry.event(
            "model_started", self.role, attempt_id=attempt, model=self.telemetry.settings.model
        )

    # Record provider usage once; cache and reasoning details are preserved without double counting.
    def on_llm_end(self, response, *, run_id, **kwargs):
        attempt = str(run_id)
        generation = response.generations[0][0]
        usage = getattr(getattr(generation, "message", None), "usage_metadata", None)
        cost = None
        if usage:
            cost = estimate_token_cost(
                self.telemetry.settings.model,
                usage["input_tokens"],
                usage["output_tokens"],
                usage.get("input_token_details", {}).get("cache_read", 0),
            )
        if usage and cost is not None:
            # Supply explicit per-call prices so new model names do not silently lose cost tracking.
            input_cost = estimate_token_cost(
                self.telemetry.settings.model,
                usage["input_tokens"],
                0,
                usage.get("input_token_details", {}).get("cache_read", 0),
            )
            usage.update(input_cost=input_cost, output_cost=cost - input_cost, total_cost=cost)
        self.telemetry.reconcile(attempt, cost)
        self.telemetry.event(
            "model_completed",
            self.role,
            attempt_id=attempt,
            usage=usage,
            estimated_cost_usd=cost,
            price_version=PRICE_VERSION,
            duration_seconds=round(perf_counter() - self.attempts.pop(attempt, perf_counter()), 6),
        )

    # Preserve unknown usage on failures rather than recording an invented zero cost.
    def on_llm_error(self, error, *, run_id, **kwargs):
        attempt = str(run_id)
        self.telemetry.event(
            "model_failed",
            self.role,
            attempt_id=attempt,
            usage=None,
            estimated_cost_usd=None,
            error_code=type(error).__name__,
            duration_seconds=round(perf_counter() - self.attempts.pop(attempt, perf_counter()), 6),
        )


# Create a parent trace only for explicitly enabled live execution; offline tests never transmit
# traces.
@contextmanager
def review_trace(settings: Settings, review: dict):
    enabled = review["execution_mode"] == "live" and settings.langsmith_tracing
    if not enabled:
        with tracing_context(enabled=False):
            yield None
        return
    if not settings.langsmith_api_key.get_secret_value():
        raise DomainError("LangSmith tracing is enabled but its API key is missing.")
    client = Client(
        api_key=settings.langsmith_api_key.get_secret_value(), api_url=settings.langsmith_endpoint
    )
    destination = (
        {
            "address": agent_address(
                settings.langsmith_agent_id, settings.langsmith_agent_environment
            )
        }
        if settings.langsmith_agent_id
        else {"project_name": settings.langsmith_project or "loandesk-development"}
    )
    metadata = {
        "case_id": review["case_id"],
        "review_id": review["id"],
        "thread_id": review["id"],
        "case_version": review["case_version"],
        "review_mode": review["review_mode"],
        "execution_mode": review["execution_mode"],
        "model": settings.model,
        "prompt_version": "loan-review-v1",
        "policy_version": "fictional-sme-v1",
    }
    with tracing_context(enabled=True, client=client):
        with trace(
            "loan_application_review",
            tags=[review["review_mode"], "live"],
            metadata=metadata,
            client=client,
            **destination,
        ) as run:
            yield run
    client.flush()
