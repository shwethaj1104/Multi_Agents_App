from loandesk.core.settings import Settings
from loandesk.domain.contracts import ApplicationInput, DomainError, LoanApplication, utc_now
from loandesk.infrastructure.document_storage.document_parser import parse_evidence
from loandesk.repositories.document_repository import DocumentRepository
from loandesk.services.sample_case_service import build_sample_case


class ApplicationService:
    # Keep case management independent of HTTP and agent implementation details.
    def __init__(self, repository: DocumentRepository, settings: Settings):
        self.repository, self.settings = repository, settings

    # Attribute legacy cases to their earliest review; untouched cases remain in Single agent.
    def workspace_for(self, record: dict) -> str:
        if record.get("workspace_mode") in ("single_agent", "multi_agent"):
            return record["workspace_mode"]
        reviews = self.repository.list("reviews", {"case_id": record["id"]})
        if reviews:
            return min(reviews, key=lambda review: (review["created_at"], review["id"]))[
                "review_mode"
            ]
        return "single_agent"

    # Return only this workspace's cases; storage remains shared without mixing architecture lists.
    def list(self) -> list[dict]:
        mode = self.settings.review_mode
        latest = {}
        for review in self.repository.list("reviews", {"review_mode": mode}):
            case_id = review["case_id"]
            if case_id not in latest or (review["created_at"], review["id"]) > (
                latest[case_id]["created_at"],
                latest[case_id]["id"],
            ):
                latest[case_id] = review
        records = []
        for record in self.repository.list("applications"):
            if self.workspace_for(record) != mode:
                continue
            review = latest.get(record["id"])
            status = "not_reviewed"
            if review:
                # Changed evidence must never display a previous sign-off as current approval.
                status = (
                    "needs_review"
                    if review.get("case_version") != record["version"]
                    else review["status"]
                )
            records.append({**record, "workspace_mode": mode, "review_status": status})
        return records

    # Reject cross-workspace case access before evidence reads, uploads or review creation.
    def get(self, case_id: str, *, workspace_mode: str | None = None) -> LoanApplication:
        record = self.repository.get("applications", case_id)
        mode = workspace_mode or self.settings.review_mode
        if record is None or self.workspace_for(record) != mode:
            raise DomainError("Application not found in this architecture workspace.", 404)
        return LoanApplication.model_validate({**record, "workspace_mode": mode})

    # Create a new saved application; evidence is uploaded separately and never invented.
    def create(
        self, payload: ApplicationInput, *, is_sample=False, workspace_mode: str | None = None
    ) -> LoanApplication:
        case = LoanApplication(
            **payload.model_dump(),
            is_sample=is_sample,
            workspace_mode=workspace_mode or self.settings.review_mode,
        )
        self.repository.insert("applications", case.model_dump(mode="json"))
        return case

    # Persist a parsed document with optimistic version checks; in-flight reviews keep immutable
    # snapshots.
    def upload(
        self,
        case_id: str,
        filename: str,
        content: bytes,
        kind: str,
        *,
        workspace_mode: str | None = None,
    ) -> LoanApplication:
        case = self.get(case_id, workspace_mode=workspace_mode)
        active = [
            review
            for review in self.repository.list("reviews", {"case_id": case_id})
            if review["status"] in ("queued", "running", "resuming")
        ]
        if active:
            raise DomainError("Wait for the active review before changing its evidence.", 409)
        if len(case.documents) >= 10:
            raise DomainError("At most ten evidence files may be attached to one case.")
        document = parse_evidence(
            filename, content, kind, self.settings.runtime_directory / "uploads"
        )
        if any(item.sha256 == document.sha256 and item.kind == kind for item in case.documents):
            (self.settings.runtime_directory / "uploads" / document.storage_name).unlink(
                missing_ok=True
            )
            raise DomainError("This evidence file is already attached.", 409)
        expected = case.version
        case.documents.append(document)
        case.version += 1
        case.updated_at = utc_now()
        if not self.repository.replace("applications", case.model_dump(mode="json"), expected):
            (self.settings.runtime_directory / "uploads" / document.storage_name).unlink(
                missing_ok=True
            )
            raise DomainError("Application changed while uploading. Refresh and try again.", 409)
        return case

    # Create one complete synthetic fixture including its labeled evidence; never run a model here.
    def create_sample(self, key: str, *, workspace_mode: str | None = None) -> LoanApplication:
        try:
            payload, files = build_sample_case(key)
        except ValueError as error:
            raise DomainError("Sample case not found.", 404) from error
        case = self.create(payload, is_sample=True, workspace_mode=workspace_mode)
        for filename, kind, content in files:
            case = self.upload(case.id, filename, content, kind, workspace_mode=workspace_mode)
        return case
