from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from loandesk.api.dependencies import require_access
from loandesk.api.routes import applications, evaluations, health, reviews, runtime
from loandesk.core.settings import Settings, get_settings
from loandesk.domain.contracts import DomainError
from loandesk.infrastructure.application_resources import ApplicationResources


# Compose the API with lifespan-owned clients; constructing an app never invokes a model.
def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings

    # Open durable stores on startup and close them only after background work has completed.
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        resources = ApplicationResources(configuration or get_settings())
        application.state.resources = resources
        resources.mark_interrupted()
        try:
            yield
        finally:
            resources.close()

    application = FastAPI(title="LoanDesk API", version="0.2.0", lifespan=lifespan)

    # Return controlled business errors without revealing credentials or provider exception
    # messages.
    @application.exception_handler(DomainError)
    async def handle_domain_error(request: Request, error: DomainError):
        return JSONResponse(status_code=error.status_code, content={"detail": str(error)})

    application.include_router(health.router, prefix="/api/v1")
    protected = APIRouter(prefix="/api/v1", dependencies=[Depends(require_access)])
    for router in (runtime.router, applications.router, reviews.router, evaluations.router):
        protected.include_router(router)
    application.include_router(protected)
    return application


app = create_app()
