from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from loandesk.core.settings import Settings
from loandesk.domain.contracts import DomainError, HumanDecision
from loandesk.infrastructure.application_resources import ApplicationResources
from loandesk.infrastructure.language_models.review_agent_runtime import ReviewAgentRuntime
from loandesk.main import create_app
from loandesk.services.sample_case_service import sample_bank_csv
from loandesk.tools.loan_review_tools import calculate_monthly_installment


# Isolate fixtures from the user's credentials, MongoDB and external tracing.
@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        storage_backend="sqlite",
        runtime_directory=tmp_path,
        langsmith_tracing=False,
        live_model_calls_enabled=False,
    )


# Treat provider construction from any offline path as a test failure.
@pytest.fixture(autouse=True)
def forbid_live_clients(monkeypatch):
    # No offline test may instantiate a model SDK client.
    def forbidden(*args, **kwargs):
        raise AssertionError("An offline path attempted provider construction.")

    monkeypatch.setattr(
        "loandesk.infrastructure.language_models.review_agent_runtime.ChatOpenAI", forbidden
    )


# Verify amortization against a fixed reference and a zero-interest scenario.
def test_financial_calculation():
    assert calculate_monthly_installment(Decimal("150000"), Decimal("8"), 36) == Decimal("4700.45")
    assert calculate_monthly_installment(Decimal("1200"), Decimal("0"), 12) == Decimal("100.00")


# Both graphs persist reports and approvals across restarts with idempotent decisions.
@pytest.mark.parametrize("mode", ["single_agent", "multi_agent"])
def test_approval_survives_restart(settings, mode):
    settings.review_mode = mode
    first = ApplicationResources(settings)
    case = first.applications.create_sample("complete")
    assert first.applications.list()[0]["review_status"] == "not_reviewed"
    review = first.reviews.start(case.id, "offline")
    first.reviews.execute(review["id"])
    pending = first.reviews.get(review["id"])
    assert pending["status"] == "awaiting_approval", pending["error"]
    assert first.applications.list()[0]["review_status"] == "awaiting_approval"
    assert pending["report"]["financials"]["monthly_installment"] == "4700.45"
    assert pending["usage"]["model_calls"] == 0
    first.close()
    restarted = ApplicationResources(settings)
    decision = HumanDecision(
        action="approve", revision=1, reviewer="Test officer", idempotency_key="one"
    )
    restarted.reviews.decide(review["id"], decision)
    restarted.reviews.execute(review["id"])
    result = restarted.reviews.get(review["id"])
    assert result["status"] == "approved", result["error"]
    assert len(result["decisions"]) == 1
    assert restarted.reviews.decide(review["id"], decision)["status"] == "approved"
    assert restarted.applications.list()[0]["review_status"] == "approved"
    restarted.applications.upload(
        case.id, "updated-bank.csv", sample_bank_csv("960000"), "bank_transactions"
    )
    assert restarted.applications.list()[0]["review_status"] == "needs_review"
    restarted.reviews.start(case.id, "offline")
    assert restarted.applications.list()[0]["review_status"] == "queued"
    restarted.close()


# Missing evidence cannot be approved; newly supplied evidence requires a fresh report revision.
def test_clarification_and_stale_approval(settings):
    resources = ApplicationResources(settings)
    case = resources.applications.create_sample("missing")
    review = resources.reviews.start(case.id, "offline")
    resources.reviews.execute(review["id"])
    assert resources.reviews.get(review["id"])["status"] == "needs_information"
    with pytest.raises(DomainError, match="blocking"):
        resources.reviews.decide(
            review["id"], HumanDecision(action="approve", revision=1, reviewer="Test officer")
        )
    resources.applications.upload(
        case.id, "bank.csv", sample_bank_csv("1200000"), "bank_transactions"
    )
    resources.reviews.decide(
        review["id"],
        HumanDecision(
            action="provide_information",
            revision=1,
            reviewer="Test officer",
            note="Missing bank evidence attached.",
        ),
    )
    resources.reviews.execute(review["id"])
    result = resources.reviews.get(review["id"])
    assert result["status"] == "awaiting_approval", result["error"]
    assert result["report"]["revision"] == 2
    with pytest.raises(DomainError, match="revision"):
        resources.reviews.decide(
            review["id"], HumanDecision(action="approve", revision=1, reviewer="Test officer")
        )
    resources.close()


# A barrier requires all specialists to enter concurrently; sequential role prompts cannot pass.
def test_parallel_specialist_dispatch(settings, monkeypatch):
    barrier = Barrier(3, timeout=5)
    original = ReviewAgentRuntime.assess

    # Synchronize the three branches while leaving supervisor execution unchanged.
    def synchronized(self, role, application, context=None):
        if role in ("document_reviewer", "financial_analyst", "policy_reviewer"):
            barrier.wait()
        return original(self, role, application, context)

    monkeypatch.setattr(ReviewAgentRuntime, "assess", synchronized)
    resources = ApplicationResources(settings)
    case = resources.applications.create_sample("complete", workspace_mode="multi_agent")
    review = resources.reviews.start(case.id, "offline", "multi_agent")
    resources.reviews.execute(review["id"])
    result = resources.reviews.get(review["id"])
    assert result["status"] == "awaiting_approval", result["error"]
    roles = {event["role"] for event in result["events"]}
    assert {"document_reviewer", "financial_analyst", "policy_reviewer"} <= roles
    resources.close()


# Atomic record versions ensure two competing human decisions cannot both succeed.
def test_competing_decisions(settings):
    resources = ApplicationResources(settings)
    case = resources.applications.create_sample("complete")
    review = resources.reviews.start(case.id, "offline")
    resources.reviews.execute(review["id"])

    # Return whether this decision won the optimistic concurrency check.
    def decide(action):
        try:
            resources.reviews.decide(
                review["id"], HumanDecision(action=action, revision=1, reviewer="Test officer")
            )
            return True
        except DomainError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(decide, ["approve", "reject"]))
    assert sum(outcomes) == 1
    resources.close()


# Public endpoints reject live calls while allowing bounded synthetic document uploads.
def test_live_gate_and_file_validation(settings):
    with TestClient(create_app(settings)) as client:
        case = client.post("/api/v1/samples/insufficient").json()
        path = f"/api/v1/applications/{case['id']}"
        assert client.post(path + "/reviews", json={"execution_mode": "live"}).status_code == 403
        assert (
            client.post("/api/v1/experiments", json={"execution_mode": "live"}).status_code == 403
        )
        assert client.post(path + "/reviews", json={}).status_code == 403
        assert client.post("/api/v1/experiments", json={}).status_code == 403
        response = client.post(
            path + "/documents",
            data={"kind": "profit_and_loss"},
            files={
                "file": (
                    "../evidence.json",
                    b'{"annual_revenue":"900000","annual_expenses":"650000","annual_debt_service":"30000"}',
                    "application/json",
                )
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["documents"][0]["filename"] == "evidence.json"
        assert (
            client.post(
                path + "/documents", data={"kind": "other"}, files={"file": ("bad.exe", b"bad")}
            ).status_code
            == 400
        )


# Initial dispatch is code-only, while all three specialists and supervisor synthesis still execute.
def test_fixed_dispatch_avoids_planning_model(settings, monkeypatch):
    resources = ApplicationResources(settings)
    roles = []
    original = ReviewAgentRuntime.assess

    # Record role invocations through the real offline graph without constructing provider clients.
    def track_roles(self, role, application, context=None):
        roles.append(role)
        return original(self, role, application, context)

    monkeypatch.setattr(ReviewAgentRuntime, "assess", track_roles)
    case = resources.applications.create_sample("complete", workspace_mode="multi_agent")
    review = resources.reviews.start(case.id, "offline", "multi_agent")
    resources.reviews.execute(review["id"])
    result = resources.reviews.get(review["id"])
    assert result["status"] == "awaiting_approval"
    assert set(roles) == {
        "document_reviewer",
        "financial_analyst",
        "policy_reviewer",
        "supervisor_synthesis",
    }
    assert len(roles) == 4
    assert any(event["role"] == "supervisor_dispatch" for event in result["events"])
    resources.close()
