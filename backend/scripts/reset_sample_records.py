"""Back up and atomically delete only sample cases and dependent development records."""

import gzip
from datetime import UTC, datetime
from pathlib import Path

from bson import json_util
from pymongo import MongoClient

from loandesk.core.settings import get_settings


# Preserve manual applications and budgets; abort if samples or experiments are still processing.
def main() -> None:
    settings = get_settings()
    with MongoClient(
        settings.mongodb_uri.get_secret_value(), serverSelectionTimeoutMS=7000
    ) as client:
        database = client[settings.mongodb_database]
        applications = list(database.applications.find({"is_sample": True}))
        case_ids = [item["id"] for item in applications]
        reviews = list(database.reviews.find({"case_id": {"$in": case_ids}}))
        review_ids = [item["id"] for item in reviews]
        experiments = list(database.experiments.find({"dataset_version": "development-v1"}))
        if any(
            item.get("status") in {"queued", "running", "resuming"}
            for item in reviews + experiments
        ):
            raise RuntimeError("Sample work is active. Stop it before resetting records.")
        records = {
            "applications": applications,
            "reviews": reviews,
            "experiments": experiments,
            "graph_checkpoints": list(
                database.graph_checkpoints.find({"thread_id": {"$in": review_ids}})
            ),
            "graph_checkpoint_writes": list(
                database.graph_checkpoint_writes.find({"thread_id": {"$in": review_ids}})
            ),
        }
        backup = (
            Path(".runtime/backups")
            / f"sample-reset-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json.gz"
        )
        backup.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(backup, "wt") as output:
            output.write(json_util.dumps({"records": records}))
        backup.chmod(0o600)

        # Detect concurrent changes; any mismatch aborts the entire removal transaction.
        def remove_samples(session):
            for name, documents in records.items():
                for document in documents:
                    if (
                        database[name].find_one({"_id": document["_id"]}, session=session)
                        != document
                    ):
                        raise RuntimeError("Records changed during backup; reset aborted.")
                result = database[name].delete_many(
                    {"_id": {"$in": [d["_id"] for d in documents]}}, session=session
                )
                if result.deleted_count != len(documents):
                    raise RuntimeError("Reset count mismatch; transaction aborted.")

        with client.start_session() as session:
            session.with_transaction(remove_samples)
        print(
            {
                "deleted": {name: len(items) for name, items in records.items()},
                "backup": str(backup),
                "manual_applications_preserved": database.applications.count_documents(
                    {"is_sample": {"$ne": True}}
                ),
            }
        )


if __name__ == "__main__":
    main()
