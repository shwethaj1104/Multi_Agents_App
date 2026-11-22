from contextlib import nullcontext
from unittest.mock import Mock

import httpx
import pytest
from langchain_openai import ChatOpenAI

from loandesk.core.settings import Settings
from loandesk.domain.contracts import LoanApplication
from loandesk.infrastructure.language_models import review_agent_runtime
from loandesk.services.sample_case_service import build_sample_case


# Inspect real SDK request conversion for every role while blocking all provider HTTP traffic.
@pytest.mark.parametrize("role", list(review_agent_runtime.ROLE_INSTRUCTIONS))
def test_reasoning_tools_use_responses_api(monkeypatch, role):
    captured = {}

    # Any unexpected HTTP attempt is an offline test failure, never a paid request.
    def reject_network(request):
        raise AssertionError("Provider HTTP traffic is forbidden in this test.")

    # Use dummy credentials and a blocked transport to inspect the installed SDK's actual payload.
    def capture_model(**kwargs):
        model = ChatOpenAI(
            **kwargs,
            http_client=httpx.Client(transport=httpx.MockTransport(reject_network)),
        )
        captured["model"] = model
        return model

    # Stop before agent execution after checking reasoning, token limits and function tool format.
    def inspect_agent(model, *, tools, **kwargs):
        assert model.use_responses_api is True
        tool_schema = {
            "type": "function",
            "function": {
                "name": "inspect_case_evidence",
                "description": "Inspect synthetic evidence.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        payload = model._get_request_payload("Review this case.", tools=[tool_schema])
        assert model._use_responses_api(payload)
        assert payload["reasoning"]["effort"] == "low"
        assert payload["max_output_tokens"] == 2048
        assert payload["tools"][0]["name"] == "inspect_case_evidence"
        assert "messages" not in payload
        raise RuntimeError("Offline payload verified")

    monkeypatch.setattr(review_agent_runtime, "ChatOpenAI", capture_model)
    monkeypatch.setattr(review_agent_runtime, "create_agent", inspect_agent)
    settings = Settings(
        _env_file=None, openai_api_key="sk-offline-test", live_model_calls_enabled=True
    )
    telemetry = Mock()
    telemetry.step.return_value = nullcontext()
    runtime = review_agent_runtime.ReviewAgentRuntime(settings, telemetry, "live")
    application, _ = build_sample_case("complete")
    with pytest.raises(RuntimeError, match="Offline payload verified"):
        runtime.assess(role, LoanApplication(**application.model_dump()))
    captured["model"].http_client.close()


# Synthesis consumes verified inputs directly but still rejects fabricated citation IDs.
@pytest.mark.parametrize("invented_citation", [False, True])
def test_synthesis_snapshot_and_citation_validation(monkeypatch, invented_citation):
    import json

    from loandesk.domain.contracts import AgentAssessment, DomainError

    monkeypatch.setattr(review_agent_runtime, "ChatOpenAI", Mock())

    # Verify the prompt supplied to the model without performing a network request.
    def respond(payload, config):
        prompt = json.loads(payload["messages"][0]["content"])
        assert prompt["verified_case"]["checks"]["financials"]["monthly_installment"] == "4700.45"
        assert prompt["verified_case"]["policy"]["clauses"]
        assert prompt["verified_case"]["evidence"]["documents"] == []
        assert prompt["source_manifest"] == []
        return {
            "structured_response": AgentAssessment(
                summary="Mock synthesis", evidence_ids=["fabricated"] if invented_citation else []
            ),
            "messages": [],
        }

    # Synthesis has no investigation tools; code already supplied their verified outputs.
    def create_synthesis(model, *, tools, **kwargs):
        assert tools == []
        return Mock(invoke=respond)

    monkeypatch.setattr(review_agent_runtime, "create_agent", create_synthesis)
    telemetry = Mock()
    telemetry.step.return_value = nullcontext()
    settings = Settings(
        _env_file=None, openai_api_key="sk-offline-test", live_model_calls_enabled=True
    )
    application, _ = build_sample_case("complete")
    runtime = review_agent_runtime.ReviewAgentRuntime(settings, telemetry, "live")
    if invented_citation:
        with pytest.raises(DomainError, match="unknown document"):
            runtime.assess("supervisor_synthesis", LoanApplication(**application.model_dump()))
    else:
        assert (
            runtime.assess("supervisor_synthesis", LoanApplication(**application.model_dump()))[
                "summary"
            ]
            == "Mock synthesis"
        )
