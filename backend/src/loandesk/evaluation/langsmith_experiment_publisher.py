from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

from langsmith import Client

from loandesk.domain.contracts import DomainError
from loandesk.repositories.document_repository import update_record


# Upload already measured paired results on explicit request; never rerun models during publication.
def publish_experiment(resources, experiment_id: str, client=None) -> dict:
    experiment = resources.repository.get("experiments", experiment_id)
    if not experiment:
        raise DomainError("Experiment not found.", 404)
    if experiment["status"] != "completed":
        raise DomainError("Finish the experiment before publishing results.", 409)
    if experiment.get("langsmith_published"):
        return experiment
    settings = resources.settings
    if client is None:
        if not settings.langsmith_api_key.get_secret_value():
            raise DomainError("LANGSMITH_API_KEY is not configured.")
        client = Client(
            api_key=settings.langsmith_api_key.get_secret_value(),
            api_url=settings.langsmith_endpoint,
        )
    dataset_name = f"loandesk-{experiment_id}"
    dataset = (
        client.read_dataset(dataset_name=dataset_name)
        if client.has_dataset(dataset_name=dataset_name)
        else client.create_dataset(
            dataset_name,
            description=experiment["interpretation"],
            metadata={
                "split": experiment["dataset_split"],
                "execution_mode": experiment["execution_mode"],
            },
        )
    )
    cases = {row["sample_key"]: row for row in experiment["rows"]}
    namespace = UUID(experiment_id)
    examples = []
    for key, row in cases.items():
        review = resources.reviews.get(row["review_id"])
        examples.append(
            {
                "id": str(uuid5(namespace, key)),
                "inputs": {"sample_key": key, "application": review["application_snapshot"]},
                "outputs": {"reference": row.get("reference", {})},
            }
        )
    client.create_examples(dataset_id=dataset.id, examples=examples)
    urls = {}
    for mode in ("single_agent", "multi_agent"):
        project_name = f"{dataset_name}-{mode}"
        project = client.create_project(
            project_name,
            reference_dataset_id=dataset.id,
            upsert=True,
            metadata={
                "review_mode": mode,
                "execution_mode": experiment["execution_mode"],
                "comparison_source": "saved_results_not_new_model_calls",
            },
        )
        urls[mode] = getattr(project, "url", None)
        for row in [item for item in experiment["rows"] if item["review_mode"] == mode]:
            run_id = uuid5(namespace, row["review_id"])
            start = datetime.now(UTC)
            client.create_run(
                "loan_review_benchmark",
                {"sample_key": row["sample_key"]},
                "chain",
                id=run_id,
                project_name=project_name,
                reference_example_id=uuid5(namespace, row["sample_key"]),
                start_time=start,
                end_time=start + timedelta(seconds=row["processing_seconds"]),
                outputs={
                    "report": resources.reviews.get(row["review_id"])["report"],
                    "measured_usage": row["usage"],
                    "source_trace_url": row.get("trace_url"),
                },
                tags=[mode, experiment["execution_mode"]],
                extra={
                    "metadata": {
                        "review_mode": mode,
                        "review_id": row["review_id"],
                        "execution_mode": experiment["execution_mode"],
                        "copied_result": True,
                    }
                },
            )
            for metric, score in row["scores"].items():
                client.create_feedback(
                    run_id=run_id,
                    key=metric,
                    score=score,
                    feedback_id=uuid5(run_id, metric),
                    extend_trace_retention=False,
                )
    client.flush()

    # Store the returned dataset URL instead of inventing a hosted-region URL.
    def mark_published(current):
        current.update(
            langsmith_dataset_url=getattr(dataset, "url", None),
            langsmith_projects=urls,
            langsmith_published=True,
        )
        return current

    return update_record(resources.repository, "experiments", experiment_id, mark_published)
