from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

from loandesk.agents.multi_agent.document_review_agent import run_document_review_agent
from loandesk.agents.multi_agent.financial_review_agent import run_financial_review_agent
from loandesk.agents.multi_agent.policy_review_agent import run_policy_review_agent
from loandesk.agents.multi_agent.supervisor_agent import run_supervisor_agent
from loandesk.agents.single_agent.loan_review_agent import run_loan_review_agent
from loandesk.domain.contracts import LoanApplication, ReviewReport
from loandesk.tools.loan_review_tools import analyze_application

SPECIALISTS = {
    "document_reviewer": run_document_review_agent,
    "financial_analyst": run_financial_review_agent,
    "policy_reviewer": run_policy_review_agent,
}


# Merge independently returned specialist assessments into one shared state without lost updates.
def merge_assessments(previous: dict, incoming: dict) -> dict:
    return {**previous, **incoming}


class ReviewState(TypedDict, total=False):
    application: dict
    results: Annotated[dict, merge_assessments]
    assignment: dict
    role: str
    report: dict
    revision: int
    feedback: str
    human_note: str
    decision: dict
    outcome: str
    evidence_changed: bool
    follow_up_rounds: int


# Assemble the same validated report contract for either architecture, retaining authoritative
# checks.
def compose_report(state: ReviewState, assessment: dict, offline: bool) -> dict:
    application = LoanApplication.model_validate(state["application"])
    checked = analyze_application(application)
    blocking = any(item["severity"] == "blocking" for item in checked["findings"])
    warning = any(item["severity"] == "warning" for item in checked["findings"])
    recommendation = (
        "needs_information" if blocking else "policy_exception" if warning else "ready_for_officer"
    )
    limitations = [
        "Fictional policy and synthetic-data portfolio workflow; no loan disbursement.",
        "Repayment is a scenario using the stated rate and term, not a credit offer.",
        "No identity, credit bureau, collateral, tax or external fraud verification was performed.",
        (
            "Evidence text is extracted, not independently authenticated. "
            "Replaced documents remain in audit history."
        ),
    ]
    if offline:
        limitations.insert(
            0,
            (
                "OFFLINE: deterministic rules exercised the workflow; no AI model "
                "or paid evaluation ran."
            ),
        )
    return ReviewReport(
        revision=state.get("revision", 0) + 1,
        title=f"Assessment — {application.business_name}",
        summary=assessment["summary"],
        recommendation=recommendation,
        agent_finding_codes=assessment.get("finding_codes", []),
        agent_evidence_ids=assessment.get("evidence_ids", []),
        human_note=state.get("human_note", ""),
        limitations=limitations,
        **checked,
    ).model_dump(mode="json")


# Build a checkpointed workflow with real LangGraph fan-out/fan-in and revision-bound human
# interrupts.
def build_loan_review_graph(review_mode: str, runtime, checkpointer):
    graph = StateGraph(ReviewState)

    # Run the whole tool investigation as one generalist while preserving equivalent output rules.
    def generalist(state):
        application = LoanApplication.model_validate(state["application"])
        result = run_loan_review_agent(
            runtime,
            application,
            {"feedback": state.get("feedback", ""), "human_note": state.get("human_note", "")},
        )
        report = compose_report(state, result, runtime.execution_mode == "offline")
        return {"results": {"generalist": result}, "report": report, "revision": report["revision"]}

    # Dispatch fixed responsibilities in code; reserve model planning for later feedback.
    def plan(state):
        if not state.get("feedback") or not state.get("results") or state.get("evidence_changed"):
            with runtime.telemetry.step("supervisor_dispatch"):
                return {
                    "assignment": {
                        "follow_up_agents": list(SPECIALISTS),
                        "summary": "Dispatch document, financial and policy reviews in parallel.",
                    }
                }
        application = LoanApplication.model_validate(state["application"])
        assignment = run_supervisor_agent(
            runtime,
            application,
            {
                "feedback": state.get("feedback", ""),
                "human_note": state.get("human_note", ""),
                "prior_results": state.get("results", {}),
            },
        )
        return {"assignment": assignment}

    # Dispatch all first-pass specialists together; later feedback can target a subset with prior
    # findings retained.
    def dispatch(state):
        targeted = state["assignment"].get("follow_up_agents", [])
        roles = (
            targeted
            if state.get("feedback")
            and state.get("results")
            and targeted
            and not state.get("evidence_changed")
            else list(SPECIALISTS)
        )
        return [Send("specialist", {**state, "role": role}) for role in roles]

    # Execute one independently dispatched role and return only its own part of shared state.
    def specialist(state):
        role = state["role"]
        result = SPECIALISTS[role](
            runtime,
            LoanApplication.model_validate(state["application"]),
            {
                "assignment": state["assignment"],
                "feedback": state.get("feedback", ""),
                "human_note": state.get("human_note", ""),
            },
        )
        return {"results": {role: result}}

    # Wait for the parallel superstep, then use the supervisor to join evidence and financial
    # policy checks.
    def synthesize(state):
        assessment = run_supervisor_agent(
            runtime,
            LoanApplication.model_validate(state["application"]),
            {
                "specialist_findings": state["results"],
                "feedback": state.get("feedback", ""),
                "human_note": state.get("human_note", ""),
            },
            synthesis=True,
        )
        report = compose_report(state, assessment, runtime.execution_mode == "offline")
        return {"report": report, "revision": report["revision"]}

    # Persist a pause before any human decision; this node is pure before interrupt so resumption
    # is safe.
    def human_review(state):
        blocking = state["report"]["recommendation"] == "needs_information"
        decision = interrupt(
            {
                "kind": "clarification" if blocking else "approval",
                "revision": state["revision"],
                "questions": [
                    item["message"]
                    for item in state["report"]["findings"]
                    if item["severity"] == "blocking"
                ],
            }
        )
        if decision["action"] in ("request_changes", "provide_information"):
            return {
                "evidence_changed": decision.get("application", state["application"])["version"]
                != state["application"]["version"],
                "application": decision.get("application", state["application"]),
                "feedback": decision["note"],
                "human_note": decision["note"],
                "decision": decision,
                "outcome": "revise",
                "follow_up_rounds": state.get("follow_up_rounds", 0) + 1,
            }
        return {
            "decision": decision,
            "outcome": "approved" if decision["action"] == "approve" else "rejected",
        }

    # Route edits back through analysis; finalized decisions leave the graph without any financial
    # side effect.
    def after_human(state):
        if state["outcome"] == "revise":
            return "plan" if review_mode == "multi_agent" else "generalist"
        return END

    graph.add_node("human_review", human_review)
    if review_mode == "single_agent":
        graph.add_node("generalist", generalist)
        graph.add_edge(START, "generalist")
        graph.add_edge("generalist", "human_review")
    else:
        graph.add_node("plan", plan)
        graph.add_node("specialist", specialist)
        graph.add_node("synthesize", synthesize)
        graph.add_edge(START, "plan")
        graph.add_conditional_edges("plan", dispatch, ["specialist"])
        graph.add_edge("specialist", "synthesize")
        graph.add_edge("synthesize", "human_review")
    graph.add_conditional_edges("human_review", after_human)
    return graph.compile(checkpointer=checkpointer)
