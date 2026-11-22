import json
from decimal import Decimal
from pathlib import Path
from statistics import mean

from loandesk.domain.contracts import DomainError, new_id, utc_now
from loandesk.repositories.document_repository import update_record

DATASET_PATH = Path(__file__).resolve().parents[4] / "evaluations/datasets/development-cases.json"


# Score agent-selected findings separately from deterministic guardrail checks in the report.
def score_review(review: dict, reference: dict) -> dict:
    report = review.get("report")
    if not report:
        return {
            "assessment_generated": 0,
            "finding_precision": 0,
            "finding_recall": 0,
            "calculation_accuracy": 0,
            "recommendation_accuracy": 0,
            "citation_validity": 0,
        }
    expected = set(reference["expected_codes"])
    actual = set(report["agent_finding_codes"]) - {"checks_complete"}
    correct = len(expected & actual)
    cited = set(report["agent_evidence_ids"])
    known = {source["id"] for source in report["sources"]}
    return {
        "assessment_generated": 1,
        "finding_precision": correct / len(actual) if actual else float(not expected),
        "finding_recall": correct / len(expected) if expected else float(not actual),
        "calculation_accuracy": int(
            abs(
                Decimal(report["financials"]["monthly_installment"])
                - Decimal(reference["expected_installment"])
            )
            <= Decimal("0.01")
        ),
        "recommendation_accuracy": int(
            report["recommendation"] == reference["expected_recommendation"]
        ),
        # This checks references only; semantic support requires separate human/LLM grounding
        # evaluation.
        "citation_validity": len(cited & known) / len(cited) if cited else float(not known),
    }


# Compute percentile latency without adding parallel agent durations together.
def percentile95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)]


class BenchmarkService:
    # Reuse the exact application and review services used by normal product requests.
    def __init__(self, resources):
        self.resources = resources
        self.repository = resources.repository

    # Create an explicitly requested experiment; live mode still requires the independent server
    # gate.
    def start(self, execution_mode: str, limit: int = 5) -> dict:
        if limit not in range(1, 6):
            raise DomainError("Choose between one and five development cases.")
        self.resources.reviews.ensure_execution_allowed(execution_mode)
        if any(item["status"] == "running" for item in self.repository.list("experiments")):
            raise DomainError("Wait for the active benchmark to finish.", 409)
        experiment = {
            "id": new_id(),
            "version": 1,
            "status": "running",
            "created_at": utc_now(),
            "execution_mode": execution_mode,
            "dataset_version": "development-v1",
            "dataset_split": "development",
            "owner_mode": self.resources.settings.review_mode,
            "case_limit": limit,
            "rows": [],
            "summary": {},
            "interpretation": "Offline workflow checks do not measure AI architecture quality."
            if execution_mode == "offline"
            else "Development-set comparison; not a held-out generalization claim.",
        }
        self.repository.insert("experiments", experiment)
        return experiment

    # Run paired reviews serially across cases; specialists inside each multi-agent review remain
    # parallel.
    def execute(self, experiment_id: str) -> None:
        experiment = self.repository.get("experiments", experiment_id)
        references = json.loads(DATASET_PATH.read_text())["cases"][: experiment["case_limit"]]
        rows = []
        try:
            for reference in references:
                for mode in ("single_agent", "multi_agent"):
                    # Keep workspaces separate while using identical sample input bytes.
                    application = self.resources.applications.create_sample(
                        reference["sample_key"], workspace_mode=mode
                    )
                    review = self.resources.reviews.start(
                        application.id, experiment["execution_mode"], mode
                    )
                    self.resources.reviews.execute(review["id"])
                    result = self.resources.reviews.get(review["id"])
                    row = {
                        "reference": reference,
                        "sample_key": reference["sample_key"],
                        "case_id": application.id,
                        "review_id": review["id"],
                        "review_mode": mode,
                        "status": result["status"],
                        "processing_seconds": result["processing_seconds"],
                        "usage": result["usage"],
                        "scores": score_review(result, reference),
                        "trace_url": result["trace_url"],
                    }
                    rows.append(row)

                    # Persist progress after each review so interrupted experiments retain
                    # completed measurements.
                    def progress(current):
                        current["rows"] = list(rows)
                        return current

                    update_record(self.repository, "experiments", experiment_id, progress)
            summary = {}
            for mode in ("single_agent", "multi_agent"):
                selected = [row for row in rows if row["review_mode"] == mode]
                costs = [row["usage"].get("estimated_cost_usd") for row in selected]
                times = sorted(row["processing_seconds"] for row in selected)
                summary[mode] = {
                    **{
                        key: mean(row["scores"][key] for row in selected)
                        for key in selected[0]["scores"]
                    },
                    "mean_seconds": mean(times),
                    "p95_seconds": percentile95(times),
                    "mean_cost_usd": mean(costs)
                    if all(cost is not None for cost in costs)
                    else None,
                    "cases": len(selected),
                }

            def finish(current):
                current.update(status="completed", summary=summary, finished_at=utc_now())
                return current

            update_record(self.repository, "experiments", experiment_id, finish)
        except Exception:

            def fail(current):
                current.update(
                    status="failed", error="Benchmark stopped; completed rows are preserved."
                )
                return current

            update_record(self.repository, "experiments", experiment_id, fail)
