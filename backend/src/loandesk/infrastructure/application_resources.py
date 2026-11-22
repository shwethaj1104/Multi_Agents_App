import sqlite3

from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.checkpoint.sqlite import SqliteSaver

from loandesk.core.settings import Settings
from loandesk.domain.contracts import DomainError, utc_now
from loandesk.infrastructure.database.connection_diagnostics import describe_mongodb_failure
from loandesk.repositories.document_repository import (
    MongoDocumentRepository,
    SqliteDocumentRepository,
)
from loandesk.services.application_service import ApplicationService
from loandesk.services.review_service import ReviewService


class ApplicationResources:
    # Initialize application records and graph checkpoints in the chosen durable store.
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.runtime_directory.mkdir(parents=True, exist_ok=True)
        self.connection = None
        if settings.resolved_storage == "mongodb":
            if not settings.mongodb_uri.get_secret_value():
                raise DomainError("MongoDB storage was selected but MONGODB_URI is blank.")
            phase = "application storage initialization"
            try:
                self.repository = MongoDocumentRepository(
                    settings.mongodb_uri.get_secret_value(), settings.mongodb_database
                )
                phase = "checkpoint initialization"
                self.checkpointer = MongoDBSaver(
                    self.repository.client,
                    db_name=settings.mongodb_database,
                    checkpoint_collection_name="graph_checkpoints",
                    writes_collection_name="graph_checkpoint_writes",
                )
            except Exception as error:
                if hasattr(self, "repository"):
                    self.repository.close()
                raise RuntimeError(
                    describe_mongodb_failure(error, phase) + " No fallback was used."
                ) from None
        else:
            self.repository = SqliteDocumentRepository(
                settings.runtime_directory / "applications.sqlite"
            )
            self.connection = sqlite3.connect(
                settings.runtime_directory / "checkpoints.sqlite",
                check_same_thread=False,
                timeout=30,
            )
            self.checkpointer = SqliteSaver(self.connection)
        self.applications = ApplicationService(self.repository, settings)
        self.reviews = ReviewService(self.repository, settings, self.checkpointer)

    # Mark unfinished work for explicit recovery; completed paused graphs need no background
    # execution.
    def mark_interrupted(self) -> None:
        for review in self.repository.list("reviews"):
            if review["review_mode"] != self.settings.review_mode or review["status"] not in (
                "running",
                "queued",
                "resuming",
            ):
                continue
            expected = review["version"]
            review.update(status="interrupted", updated_at=utc_now(), version=expected + 1)
            self.repository.replace("reviews", review, expected)

        for experiment in self.repository.list("experiments"):
            if (
                experiment.get("owner_mode") != self.settings.review_mode
                or experiment["status"] != "running"
            ):
                continue
            expected = experiment["version"]
            experiment.update(
                status="interrupted",
                version=expected + 1,
                error=(
                    "Server restarted. Completed rows are preserved; "
                    "start a new comparison explicitly."
                ),
            )
            self.repository.replace("experiments", experiment, expected)

    # Release checkpoint connections and repository clients after outstanding tasks complete.
    def close(self) -> None:
        if self.connection:
            self.connection.close()
        self.repository.close()
