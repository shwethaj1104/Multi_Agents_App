from concurrent.futures import ThreadPoolExecutor

import pytest

from loandesk.core.settings import Settings
from loandesk.domain.contracts import DomainError
from loandesk.evaluation.benchmark_service import BenchmarkService
from loandesk.infrastructure.application_resources import ApplicationResources
from loandesk.infrastructure.observability.review_telemetry import (
    ReviewTelemetry,
    estimate_token_cost,
)
from loandesk.services.review_service import safe_review_error, summarize_usage


# Paired workflow checks use real graphs but make no AI quality claim or live model call.
def test_offline_paired_benchmark(tmp_path):
    settings = Settings(_env_file=None, storage_backend="sqlite", runtime_directory=tmp_path)
    resources = ApplicationResources(settings)
    service = BenchmarkService(resources)
    experiment = service.start("offline", 5)
    service.execute(experiment["id"])
    result = resources.repository.get("experiments", experiment["id"])
    assert result["status"] == "completed", result.get("error")
    assert len(result["rows"]) == 10
    for mode in ("single_agent", "multi_agent"):
        assert result["summary"][mode]["finding_recall"] == 1
        assert result["summary"][mode]["calculation_accuracy"] == 1
        assert result["summary"][mode]["mean_cost_usd"] == 0
    resources.close()


# Never double-count reasoning tokens or treat unavailable provider usage as zero cost.
def test_usage_accounting():
    assert estimate_token_cost("gpt-5.6-luna", 20000, 4000) == pytest.approx(0.0088)
    events = [
        {
            "name": "model_completed",
            "usage": {
                "input_tokens": 20,
                "output_tokens": 10,
                "output_token_details": {"reasoning": 5},
            },
            "estimated_cost_usd": 0.1,
        }
    ]
    assert summarize_usage(events, "live")["output_tokens"] == 10
    events.append({"name": "model_failed", "usage": None})
    assert summarize_usage(events, "live")["estimated_cost_usd"] is None


# Specialists reserve against one shared allowance, preventing concurrent double-spending.
def test_atomic_budget_reservations(tmp_path):
    settings = Settings(
        _env_file=None,
        storage_backend="sqlite",
        runtime_directory=tmp_path,
        review_budget_usd=0.004,
        session_budget_usd=0.004,
    )
    resources = ApplicationResources(settings)
    telemetry = ReviewTelemetry(resources.repository, "test-review", settings)

    # Capture whether an individual branch obtained the remaining allowance.
    def reserve(identifier):
        try:
            telemetry.reserve(identifier, 1000)
            return True
        except DomainError:
            return False

    with ThreadPoolExecutor(max_workers=3) as pool:
        outcomes = list(pool.map(reserve, ["a", "b", "c"]))
    assert sum(outcomes) == 1
    resources.close()


# Authentication guidance must identify the fix without leaking provider exception contents.
def test_safe_authentication_error():
    authentication_error = type("OpenAIAuthenticationError", (Exception,), {})
    message = safe_review_error(authentication_error("private-key-and-request"))
    assert "OpenAI authentication failed" in message
    assert "restart both backends" in message
    assert "private-key-and-request" not in message
    assert "private-key-and-request" not in safe_review_error(ValueError("private-key-and-request"))
