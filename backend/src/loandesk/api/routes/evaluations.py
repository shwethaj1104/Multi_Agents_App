import csv
import io
import json
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from loandesk.api.dependencies import get_resources
from loandesk.domain.contracts import DomainError, ExecutionMode, ExperimentRecord
from loandesk.evaluation.benchmark_service import BenchmarkService

router = APIRouter(tags=["evaluations"])


class ExperimentRequest(BaseModel):
    execution_mode: ExecutionMode = "live"
    case_limit: int = Field(default=5, ge=1, le=5)


# Return actual persisted experiments; no seeded comparison scores are displayed.
@router.get("/experiments", response_model=list[ExperimentRecord])
def list_experiments(resources=Depends(get_resources)):
    return resources.repository.list("experiments")


# Run the same labeled cases through both architectures in a paired development experiment.
@router.post("/experiments", status_code=202, response_model=ExperimentRecord)
def start_experiment(
    payload: ExperimentRequest, tasks: BackgroundTasks, resources=Depends(get_resources)
):
    service = BenchmarkService(resources)
    experiment = service.start(payload.execution_mode, payload.case_limit)
    tasks.add_task(service.execute, experiment["id"])
    return experiment


# Read a partially completed or final benchmark to support progress polling.
@router.get("/experiments/{experiment_id}", response_model=ExperimentRecord)
def get_experiment(experiment_id: str, resources=Depends(get_resources)):
    experiment = resources.repository.get("experiments", experiment_id)
    if not experiment:
        raise DomainError("Experiment not found.", 404)
    return experiment


# Export measured rows as JSON or CSV for reproducible portfolio analysis.
@router.get("/experiments/{experiment_id}/export")
def export_experiment(
    experiment_id: str, format: Literal["json", "csv"] = "json", resources=Depends(get_resources)
):
    experiment = get_experiment(experiment_id, resources)
    if format == "json":
        return Response(
            json.dumps(experiment, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="loandesk-experiment.json"'},
        )
    buffer = io.StringIO()
    fields = [
        "sample_key",
        "review_mode",
        "status",
        "processing_seconds",
        "estimated_cost_usd",
        "finding_precision",
        "finding_recall",
        "calculation_accuracy",
        "recommendation_accuracy",
        "citation_validity",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in experiment["rows"]:
        writer.writerow(
            {
                key: row.get(key, row.get("scores", {}).get(key, row.get("usage", {}).get(key)))
                for key in fields
            }
        )
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="loandesk-experiment.csv"'},
    )


# Publish existing synthetic measurements to LangSmith without running models or paid judges.
@router.post("/experiments/{experiment_id}/publish", response_model=ExperimentRecord)
def publish_results(experiment_id: str, resources=Depends(get_resources)):
    from loandesk.evaluation.langsmith_experiment_publisher import publish_experiment

    try:
        return publish_experiment(resources, experiment_id)
    except DomainError:
        raise
    except Exception:
        raise DomainError(
            "LangSmith publication failed. Check key permissions and workspace access.", 502
        ) from None
