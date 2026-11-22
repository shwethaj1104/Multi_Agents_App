from fastapi import APIRouter, Depends

from loandesk.api.dependencies import get_resources
from loandesk.domain.contracts import RuntimeDetails

router = APIRouter(tags=["runtime"])


# Show safe runtime capabilities, never keys, database URIs or private configuration values.
@router.get("/runtime", response_model=RuntimeDetails)
def get_runtime(resources=Depends(get_resources)):
    settings = resources.settings
    return {
        "review_mode": settings.review_mode,
        "implementation_stage": "application",
        "storage": settings.resolved_storage,
        "model": settings.model,
        "live_calls_enabled": settings.live_model_calls_enabled
        and bool(settings.openai_api_key.get_secret_value()),
        "tracing_configured": settings.langsmith_tracing
        and bool(settings.langsmith_api_key.get_secret_value()),
        "authentication": "workspace_token"
        if settings.access_token.get_secret_value()
        else "local_single_operator",
        "policy_version": "fictional-sme-v1",
    }
