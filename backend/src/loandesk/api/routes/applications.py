from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response

from loandesk.api.dependencies import get_resources
from loandesk.domain.contracts import (
    ApplicationInput,
    ApplicationSummary,
    DocumentKind,
    DomainError,
    LoanApplication,
    SampleTemplate,
)
from loandesk.infrastructure.document_storage.document_parser import MAX_UPLOAD_BYTES
from loandesk.services.sample_case_service import SAMPLES, build_sample_case

router = APIRouter(tags=["applications"])


# List saved applications without sending document contents in the table response.
@router.get("/applications", response_model=list[ApplicationSummary])
def list_applications(resources=Depends(get_resources)):
    return [
        {key: value for key, value in item.items() if key != "documents"}
        | {"document_count": len(item.get("documents", []))}
        for item in resources.applications.list()
    ]


# Create a saved case from validated business and loan scenario inputs.
@router.post("/applications", status_code=201, response_model=LoanApplication)
def create_application(payload: ApplicationInput, resources=Depends(get_resources)):
    return resources.applications.create(payload)


# Read a case with its extracted evidence for an officer to inspect before approving a memo.
@router.get("/applications/{case_id}", response_model=LoanApplication)
def get_application(case_id: str, resources=Depends(get_resources)):
    return resources.applications.get(case_id)


# Store one bounded evidence upload; replacing financial evidence creates a new case version.
@router.post("/applications/{case_id}/documents", status_code=201, response_model=LoanApplication)
async def upload_document(
    case_id: str,
    kind: Annotated[DocumentKind, Form()],
    file: Annotated[UploadFile, File()],
    resources=Depends(get_resources),
):
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    return resources.applications.upload(case_id, file.filename or "document", content, kind)


# Return source bytes from a server-owned storage key; clients never choose arbitrary file paths.
@router.get("/applications/{case_id}/documents/{document_id}/download")
def download_document(case_id: str, document_id: str, resources=Depends(get_resources)):
    case = resources.applications.get(case_id)
    document = next((item for item in case.documents if item.id == document_id), None)
    if not document:
        raise DomainError("Evidence document not found.", 404)
    file = resources.settings.runtime_directory / "uploads" / document.storage_name
    if not file.exists():
        raise DomainError(
            "Source file is unavailable; its extracted evidence is still stored.", 404
        )
    return Response(
        file.read_bytes(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="evidence' + file.suffix + '"'},
    )


# Describe available synthetic cases without implying any agent review has already run.
@router.get("/samples", response_model=list[SampleTemplate])
def list_samples():
    return [{key: item[key] for key in ("key", "business_name", "description")} for item in SAMPLES]


# Create an independent saved copy of a sample with its supporting documents.
@router.post("/samples/{sample_key}", status_code=201, response_model=LoanApplication)
def create_sample(sample_key: str, resources=Depends(get_resources)):
    return resources.applications.create_sample(sample_key)


# Download sample evidence as a zip so users can try the actual upload flow.
@router.get("/sample-kit")
def download_sample_kit():
    import io
    import zipfile

    buffer = io.BytesIO()
    _, files = build_sample_case("complete")
    with zipfile.ZipFile(buffer, "w") as archive:
        for filename, _, content in files:
            archive.writestr(filename, content)
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="loandesk-synthetic-evidence.zip"'},
    )
