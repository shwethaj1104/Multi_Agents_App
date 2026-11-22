import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from loandesk.core.settings import Settings
from loandesk.main import create_app


# Each independently launched workspace reports its configured architecture without credentials.
@pytest.mark.parametrize("mode", ["single_agent", "multi_agent"])
def test_runtime_uses_configured_mode(mode, tmp_path):
    settings = Settings(
        _env_file=None, review_mode=mode, storage_backend="sqlite", runtime_directory=tmp_path
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/runtime")
    assert response.json()["review_mode"] == mode
    assert response.json()["live_calls_enabled"] is False
    assert "api_key" not in response.text


# Unknown modes must fail rather than silently falling back to an architecture.
def test_unknown_mode_rejected():
    with pytest.raises(ValidationError):
        Settings(review_mode="unknown", _env_file=None)
