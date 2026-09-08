import os
import tempfile
from pathlib import Path

TEST_DIRECTORY = Path(tempfile.mkdtemp(prefix="mccia-tests-"))
os.environ["DATABASE_URL"] = "sqlite:///" + (TEST_DIRECTORY / "test.db").as_posix()
os.environ["STORAGE_PATH"] = str(TEST_DIRECTORY / "storage")
os.environ["DEMO_SEED"] = "true"
os.environ["ADMIN_PASSWORD"] = "Mccia@2026!"
os.environ["MANAGER_PASSWORD"] = "Manager@2026!"
os.environ["VIEWER_PASSWORD"] = "Viewer@2026!"

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin(client):
    response = client.post("/api/auth/login", json={"email": "admin@mccia.org", "password": "Mccia@2026!"})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def workspace(admin):
    response = admin.post("/api/workspaces", json={"name": "Integration tests", "description": "Isolated test workspace"})
    assert response.status_code == 201, response.text
    workspace_id = response.json()["id"]
    yield workspace_id
    admin.post("/api/auth/login", json={"email": "admin@mccia.org", "password": "Mccia@2026!"})
    response = admin.delete(f"/api/workspaces/{workspace_id}")
    assert response.status_code == 200, response.text
