from fastapi.testclient import TestClient

from loandesk.core.settings import Settings
from loandesk.main import create_app


# Separate architecture APIs share storage but must not read, mutate or review each other's cases.
def test_application_lists_and_access_are_architecture_scoped(tmp_path):
    common = {"_env_file": None, "storage_backend": "sqlite", "runtime_directory": tmp_path}
    with TestClient(create_app(Settings(**common, review_mode="single_agent"))) as single:
        single_case = single.post("/api/v1/samples/complete").json()
        assert single_case["workspace_mode"] == "single_agent"
        with TestClient(create_app(Settings(**common, review_mode="multi_agent"))) as multi:
            multi_case = multi.post("/api/v1/samples/missing").json()
            assert multi_case["workspace_mode"] == "multi_agent"
            assert [case["id"] for case in single.get("/api/v1/applications").json()] == [
                single_case["id"]
            ]
            assert [case["id"] for case in multi.get("/api/v1/applications").json()] == [
                multi_case["id"]
            ]
            assert multi.get(f"/api/v1/applications/{single_case['id']}").status_code == 404
            assert single.get(f"/api/v1/applications/{multi_case['id']}").status_code == 404
            path = f"/api/v1/applications/{single_case['id']}"
            assert (
                multi.post(path + "/reviews", json={"execution_mode": "offline"}).status_code == 404
            )
            assert (
                multi.post(
                    path + "/documents",
                    data={"kind": "other"},
                    files={"file": ("note.txt", b"synthetic note")},
                ).status_code
                == 404
            )


# Preserve legacy unassigned cases in Single agent without deleting or duplicating them.
def test_legacy_unassigned_cases_are_preserved(tmp_path):
    settings = Settings(_env_file=None, storage_backend="sqlite", runtime_directory=tmp_path)
    with TestClient(create_app(settings)) as client:
        case = client.post("/api/v1/samples/complete").json()
        repository = client.app.state.resources.repository
        stored = repository.get("applications", case["id"])
        version = stored["version"]
        stored.pop("workspace_mode")
        stored["version"] += 1
        assert repository.replace("applications", stored, version)
        assert client.get(f"/api/v1/applications/{case['id']}").status_code == 200
        assert client.get("/api/v1/applications").json()[0]["workspace_mode"] == "single_agent"
