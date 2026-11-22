import secrets
from typing import Annotated

from fastapi import Header, Request

from loandesk.domain.contracts import DomainError


# Supply the lifespan-managed services without constructing clients on individual API requests.
def get_resources(request: Request):
    return request.app.state.resources


# Enforce an optional server access token; local mode is explicitly an unauthenticated
# single-operator sandbox.
def require_access(request: Request, authorization: Annotated[str | None, Header()] = None):
    expected = request.app.state.resources.settings.access_token.get_secret_value()
    if expected and not secrets.compare_digest(authorization or "", f"Bearer {expected}"):
        raise DomainError("A valid workspace access token is required.", 401)
