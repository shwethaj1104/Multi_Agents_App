from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Process liveness only; external integrations are not configured yet."""
    return HealthResponse(status="ok")
