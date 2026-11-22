import hashlib
import io
import json
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader

from loandesk.domain.contracts import DomainError, EvidenceDocument

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARACTERS = 60000


# Parse supported evidence without running document instructions; reject oversized or unreadable
# files.
def parse_evidence(filename: str, content: bytes, kind: str, directory: Path) -> EvidenceDocument:
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise DomainError("Upload a non-empty file smaller than 5 MB.", 413)
    filename = Path(filename.replace("\\", "/")).name[:180]
    extension = Path(filename).suffix.lower()
    pages = 1
    try:
        if extension == ".pdf":
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted or len(reader.pages) > 50:
                raise DomainError("Use an unencrypted PDF with at most 50 pages.")
            pages = len(reader.pages)
            text = "\n".join(
                f"[Page {index + 1}]\n{page.extract_text() or ''}"
                for index, page in enumerate(reader.pages)
            )
        elif extension in (".csv", ".json", ".txt"):
            text = content.decode("utf-8-sig")
            if extension == ".json":
                json.loads(text)
        else:
            raise DomainError("Supported files: text PDF, CSV, JSON and TXT.")
    except DomainError:
        raise
    except Exception as error:
        raise DomainError(
            "This file could not be read. Use an unencrypted text document."
        ) from error
    if not text.strip() or len(text) > MAX_TEXT_CHARACTERS:
        raise DomainError(
            "Document text must be readable and at most 60000 characters. OCR is not enabled."
        )
    directory.mkdir(parents=True, exist_ok=True)
    storage_name = f"{uuid4()}{extension}"
    (directory / storage_name).write_bytes(content)
    return EvidenceDocument(
        filename=filename,
        kind=kind,
        text=text,
        pages=pages,
        storage_name=storage_name,
        sha256=hashlib.sha256(content).hexdigest(),
    )
