from datetime import datetime
from time import perf_counter

from langgraph.types import Command

from loandesk.core.settings import Settings
from loandesk.domain.contracts import (
    DomainError,
    HumanDecision,
    ReviewRecord,
    utc_now,
)
from loandesk.infrastructure.language_models.review_agent_runtime import ReviewAgentRuntime
from loandesk.infrastructure.observability.review_telemetry import ReviewTelemetry, review_trace
from loandesk.repositories.document_repository import DocumentRepository, update_record
from loandesk.services.application_service import ApplicationService
from loandesk.workflows.loan_review_graph import build_loan_review_graph


# Explain authentication failures without exposing provider messages, credentials or request data.
def safe_review_error(error: Exception) -> str:
    if isinstance(error, DomainError):
        return str(error)
    authentication_names = {"AuthenticationError", "OpenAIAuthenticationError"}
    if authentication_names.intersection(cls.__name__ for cls in type(error).__mro__):
        return (
            "OpenAI authentication failed. Check OPENAI_API_KEY in backend/.env, "
            "then restart both backends before starting a new review. "
            "Do not paste your key into the app or chat."
        )
    return "Review could not complete. Inspect the safe timeline and retry with a new review."


# Sum only leaf model-attempt usage; missing usage remains explicitly unknown.
def summarize_usage(events: list[dict], execution_mode: str) -> dict:
    completed = [event for event in events if event["name"] in ("model_completed", "model_failed")]
    known = [event for event in completed if event.get("usage") is not None]
    return {
        "model_calls": len(completed),
        "input_tokens": sum(event["usage"]["input_tokens"] for event in known),
        "output_tokens": sum(event["usage"]["output_tokens"] for event in known),
        "unknown_usage_calls": len(completed) - len(known),
        "estimated_cost_usd": None
        if len(completed) != len(known)
        else sum(event.get("estimated_cost_usd") or 0 for event in known),
        "cost_kind": "offline_no_model_calls"
        if execution_mode == "offline"
        else "provider_token_estimate",
    }


class ReviewService:
    # Share durable records and checkpoints across independent API process launches.
    def __init__(self, repository: DocumentRepository, settings: Settings, checkpointer):
        self.repository, self.settings, self.checkpointer = repository, settings, checkpointer
        self.applications = ApplicationService(repository, settings)

    # Fetch a review without ever deriving a checkpoint ID from an arbitrary client-provided
    # thread key.
    def get(self, review_id: str) -> dict:
        record = self.repository.get("reviews", review_id)
        if record is None:
            raise DomainError("Review not found.", 404)
        return record

    # Reject live execution before creating any model client or starting a background task.
    def ensure_execution_allowed(self, execution_mode: str) -> None:
        if execution_mode == "live":
            if not self.settings.live_model_calls_enabled:
                raise DomainError(
                    "Live model calls are disabled. Offline review is available.", 403
                )
            if not self.settings.openai_api_key.get_secret_value():
                raise DomainError("OPENAI_API_KEY is missing. No model call was made.", 403)

    # Snapshot evidence for one run so later uploads cannot silently change a report under review.
    def start(self, case_id: str, execution_mode: str, review_mode: str | None = None) -> dict:
        self.ensure_execution_allowed(execution_mode)
        mode = review_mode or self.settings.review_mode
        case = self.applications.get(case_id, workspace_mode=mode)
        active = [
            review
            for review in self.repository.list("reviews", {"case_id": case_id, "review_mode": mode})
            if review["status"] in ("queued", "running", "resuming")
        ]
        if active:
            raise DomainError("A review of this application is already running in this mode.", 409)
        record = ReviewRecord(
            case_id=case_id,
            case_version=case.version,
            review_mode=mode,
            execution_mode=execution_mode,
        ).model_dump(mode="json")
        record["application_snapshot"] = case.model_dump(mode="json")
        self.repository.insert("reviews", record)
        return record

    # Validate report revision, case revision and action before persisting an idempotent resume
    # command.
    def decide(self, review_id: str, decision: HumanDecision) -> dict:
        current = self.get(review_id)
        existing = next(
            (
                item
                for item in current["decisions"]
                if item["idempotency_key"] == decision.idempotency_key
            ),
            None,
        )
        if existing:
            if any(existing[key] != value for key, value in decision.model_dump().items()):
                raise DomainError("This decision key was already used for different content.", 409)
            return current
        if (
            current["status"] not in ("awaiting_approval", "needs_information")
            or not current["report"]
        ):
            raise DomainError("This review is not awaiting a human decision.", 409)
        if decision.revision != current["report"]["revision"]:
            raise DomainError("Report revision changed. Review the latest version.", 409)
        case = self.applications.get(current["case_id"])
        if decision.action == "approve" and case.version != current["case_version"]:
            raise DomainError(
                "Evidence changed. Submit an information update to generate a fresh report.", 409
            )
        if decision.action == "approve" and current["status"] == "needs_information":
            raise DomainError(
                "Resolve blocking evidence gaps before approving this assessment.", 409
            )
        if decision.action in ("request_changes", "provide_information"):
            if (
                len(
                    [
                        item
                        for item in current["decisions"]
                        if item["action"] in ("request_changes", "provide_information")
                    ]
                )
                >= 5
            ):
                raise DomainError(
                    "Five revision rounds reached. Close this review and start a fresh one.", 409
                )
            if not decision.note.strip():
                raise DomainError("Explain the requested changes or new information.")
            if (
                decision.action == "provide_information"
                and case.version == current["case_version"]
                and current["status"] == "needs_information"
            ):
                raise DomainError(
                    "Upload new supporting evidence first. A note cannot replace "
                    "missing financial evidence."
                )
        command = decision.model_dump()
        command["application"] = case.model_dump(mode="json")
        command["recorded_at"] = utc_now()
        expected = current["version"]
        if current.get("waiting_since"):
            current["human_wait_seconds"] += (
                datetime.fromisoformat(utc_now()) - datetime.fromisoformat(current["waiting_since"])
            ).total_seconds()
        current.update(
            status="resuming",
            pending_resume=command,
            waiting_since=None,
            updated_at=utc_now(),
            version=expected + 1,
            decisions=[
                *current["decisions"],
                {
                    **decision.model_dump(),
                    "recorded_at": utc_now(),
                    "identity_source": "local_operator_assertion",
                },
            ],
        )
        if not self.repository.replace("reviews", current, expected):
            raise DomainError("Another decision was submitted first. Refresh the review.", 409)
        return current

    # Run or resume a graph; every pause, report and decision remains available after server
    # restart.
    def execute(self, review_id: str) -> None:
        record = self.get(review_id)
        if record["status"] not in ("queued", "resuming", "interrupted"):
            return
        expected = record["version"]
        record.update(status="running", updated_at=utc_now(), version=expected + 1)
        if not self.repository.replace("reviews", record, expected):
            return
        telemetry = ReviewTelemetry(self.repository, review_id, self.settings)
        runtime = ReviewAgentRuntime(self.settings, telemetry, record["execution_mode"])
        graph = build_loan_review_graph(record["review_mode"], runtime, self.checkpointer)
        config = {
            "configurable": {"thread_id": review_id},
            "recursion_limit": 60,
            "tags": [record["review_mode"], record["execution_mode"]],
            "metadata": {
                "review_mode": record["review_mode"],
                "review_id": review_id,
                "case_id": record["case_id"],
                "model": self.settings.model,
            },
        }
        started = perf_counter()
        try:
            self.ensure_execution_allowed(record["execution_mode"])
            with review_trace(self.settings, record) as root:
                if root:
                    # Save only an identifier and generated URL; credentials stay inside the
                    # tracing client.
                    def attach_trace(current):
                        current.update(trace_id=str(root.id), trace_url=root.get_url())
                        return current

                    update_record(self.repository, "reviews", review_id, attach_trace)
                snapshot = graph.get_state(config)
                payload = (
                    Command(resume=record["pending_resume"])
                    if record.get("pending_resume") and snapshot.next
                    else None
                )
                if not snapshot.values:
                    payload = {
                        "application": record["application_snapshot"],
                        "results": {},
                        "revision": 0,
                        "follow_up_rounds": 0,
                    }
                graph.invoke(payload, config=config, durability="sync")
                snapshot = graph.get_state(config)
                state = snapshot.values
                paused = bool(snapshot.next)
                report = state.get("report")
                status = (
                    (
                        "needs_information"
                        if report and report["recommendation"] == "needs_information"
                        else "awaiting_approval"
                    )
                    if paused
                    else state.get("outcome", "failed")
                )

                # Merge lifecycle data produced by parallel nodes instead of replacing it with an
                # old copy.
                def finish(current):
                    current.update(
                        status=status,
                        report=report,
                        pending_resume=None,
                        error=None,
                        case_version=state["application"]["version"],
                        application_snapshot=state["application"],
                        processing_seconds=current["processing_seconds"] + perf_counter() - started,
                        waiting_since=utc_now() if paused else None,
                        updated_at=utc_now(),
                    )
                    current["usage"] = summarize_usage(current["events"], current["execution_mode"])
                    return current

                update_record(self.repository, "reviews", review_id, finish)
        except Exception as error:
            # Public error strings are controlled here; provider and connection messages may
            # contain secrets.
            message = safe_review_error(error)

            def fail(current):
                current.update(
                    status="failed",
                    error=message,
                    updated_at=utc_now(),
                    processing_seconds=current["processing_seconds"] + perf_counter() - started,
                )
                current["usage"] = summarize_usage(current["events"], current["execution_mode"])
                return current

            update_record(self.repository, "reviews", review_id, fail)

    # Expose explicit recovery after a process interruption; never replay paid calls automatically.
    def recover(self, review_id: str) -> dict:
        record = self.get(review_id)
        if record["status"] != "interrupted":
            raise DomainError("Only interrupted reviews can be recovered.", 409)
        self.ensure_execution_allowed(record["execution_mode"])
        return record
