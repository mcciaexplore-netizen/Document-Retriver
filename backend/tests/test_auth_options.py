import json
from collections import defaultdict, deque

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.database import Base, get_db, install_search_index
from app.main import app
from app.models import AuditLog, LoginSession, Membership, User, Workspace
from app.security import hash_password, verify_password


DEMO_ACCOUNTS = [
    {"email": "admin@mccia.org", "password": "Mccia@2026!", "role": "Admin"},
    {"email": "manager@mccia.org", "password": "Manager@2026!", "role": "Manager"},
    {"email": "viewer@mccia.org", "password": "Viewer@2026!", "role": "Viewer"},
]


@pytest.fixture
def auth_client(monkeypatch, tmp_path):
    # An independent database keeps these account mutations out of both the
    # running application and the other workflow tests' seeded database.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        install_search_index(connection)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        for account in DEMO_ACCOUNTS:
            db.add(User(name=account["role"], email=account["email"], role=account["role"], password_hash=hash_password(account["password"])))
        db.commit()

    def isolated_db():
        with sessions() as db:
            yield db

    monkeypatch.setattr(config, "DEMO_SEED", True)
    monkeypatch.setattr(config, "ALLOW_REGISTRATION", True)
    monkeypatch.setattr(config, "STORAGE_PATH", tmp_path)
    monkeypatch.setattr("app.indexing.STORAGE_PATH", tmp_path)
    monkeypatch.setattr("app.indexing.SessionLocal", sessions)
    monkeypatch.setattr("app.main.registration_attempts", defaultdict(deque))
    monkeypatch.setitem(app.dependency_overrides, get_db, isolated_db)
    test_client = TestClient(app)
    yield test_client, sessions
    test_client.close()
    engine.dispose()


def test_public_options_offer_working_demo_accounts(auth_client):
    client, _ = auth_client
    assert client.get("/api/auth/me").status_code == 401
    response = client.get("/api/auth/options")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"account_creation": "self_service", "allow_registration": True, "demo_accounts": DEMO_ACCOUNTS}
    for account in response.json()["demo_accounts"]:
        login = client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
        assert login.status_code == 200
        assert client.get("/api/auth/me").json()["role"] == account["role"]
        assert client.post("/api/auth/logout").status_code == 200

    unknown = client.post("/api/auth/login", json={"email": "unprovisioned@mccia.com", "password": "Mccia@2026!"})
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == "The email or password is incorrect."
    assert client.get("/api/auth/me").status_code == 401


def test_options_disable_demo_accounts(auth_client, monkeypatch):
    client, _ = auth_client
    monkeypatch.setattr(config, "DEMO_SEED", False)
    assert client.get("/api/auth/options").json() == {"account_creation": "self_service", "allow_registration": True, "demo_accounts": []}


@pytest.mark.parametrize("field,value", [
    ("password_hash", hash_password("Administrator-changed-password!")),
    ("role", "Viewer"),
    ("email", "custom-admin@example.com"),
])
def test_options_omit_changed_demo_account(auth_client, field, value, monkeypatch):
    client, sessions = auth_client
    monkeypatch.setenv("ADMIN_EMAIL", "custom-admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "Private-environment-password!")
    with sessions() as db:
        admin = db.query(User).filter_by(email="admin@mccia.org").one()
        setattr(admin, field, value)
        db.commit()
    response = client.get("/api/auth/options")
    assert response.status_code == 200
    assert response.json()["demo_accounts"] == DEMO_ACCOUNTS[1:]
    assert "custom-admin@example.com" not in response.text
    assert "Private-environment-password!" not in response.text
    assert "Administrator-changed-password!" not in response.text


def test_options_do_not_create_missing_accounts(auth_client):
    client, sessions = auth_client
    with sessions() as db:
        db.query(User).delete()
        db.commit()
    assert client.get("/api/auth/options").json()["demo_accounts"] == []
    with sessions() as db:
        assert db.query(User).count() == 0


NEW_ACCOUNT = {"name": "  New Member  ", "email": "  New.Member@Example.COM  ", "password": "My-private-password!"}


def test_register_signs_in_with_private_workspace_and_upload_access(auth_client):
    client, sessions = auth_client
    with sessions() as db:
        existing = Workspace(name="Existing confidential workspace")
        db.add(existing)
        db.commit()
        existing_id = existing.id
    response = client.post("/api/auth/register", json=NEW_ACCOUNT)
    assert response.status_code == 201, response.text
    account = response.json()["user"]
    workspace = response.json()["workspace"]
    assert account["name"] == "New Member"
    assert account["email"] == "new.member@example.com"
    assert account["role"] == "Manager"
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").json() == account
    assert [item["id"] for item in client.get("/api/workspaces").json()] == [workspace["id"]]
    assert client.get("/api/files", params={"workspace_id": existing_id}).status_code == 404
    denied = client.post("/api/files/upload", data={"workspace_id": existing_id}, files=[("files", ("denied.csv", b"ID,Value\n1,Denied\n"))])
    assert denied.status_code == 404
    uploaded = client.post("/api/files/upload", data={"workspace_id": workspace["id"]}, files=[("files", ("own.csv", b"ID,Value\n1,Owned\n"))])
    assert uploaded.status_code == 202, uploaded.text
    assert not uploaded.json()["errors"]
    file_id = uploaded.json()["files"][0]["id"]
    assert client.get(f"/api/files/{file_id}").json()["status"] == "indexed"
    assert client.post("/api/users", json={"name": "Unauthorized", "email": "forbidden@example.com", "password": "Cannot-create-admin!", "role": "Admin"}).status_code == 403
    assert client.post("/api/workspaces", json={"name": "Unauthorized"}).status_code == 403
    assert client.post(f"/api/workspaces/{existing_id}/members", json={"user_id": account["id"]}).status_code == 403
    with sessions() as db:
        stored = db.get(User, account["id"])
        assert stored.password_hash != NEW_ACCOUNT["password"]
        assert verify_password(NEW_ACCOUNT["password"], stored.password_hash)
        assert [item.workspace_id for item in db.query(Membership).filter_by(user_id=account["id"])] == [workspace["id"]]
        events = db.query(AuditLog).filter_by(user_id=account["id"]).all()
        assert {"register", "workspace_created"}.issubset({item.action for item in events})
        assert NEW_ACCOUNT["password"] not in json.dumps([item.details_json for item in events])
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    login = client.post("/api/auth/login", json={"email": NEW_ACCOUNT["email"], "password": NEW_ACCOUNT["password"]})
    assert login.status_code == 200
    assert client.get("/api/auth/me").json() == account


def test_registration_disabled_is_advertised_and_enforced(auth_client, monkeypatch):
    client, sessions = auth_client
    monkeypatch.setattr(config, "ALLOW_REGISTRATION", False)
    options = client.get("/api/auth/options").json()
    assert options["account_creation"] == "admin_managed"
    assert options["allow_registration"] is False
    assert client.post("/api/auth/register", json=NEW_ACCOUNT).status_code == 403
    with sessions() as db:
        assert db.query(User).count() == 3
        assert db.query(Workspace).count() == 0


@pytest.mark.parametrize("invalid", [
    {"role": "Admin"},
    {"workspace_id": 1},
    {"name": "   "},
    {"name": "N" * 121},
    {"email": "not-an-email"},
    {"email": "member@-invalid.com"},
    {"email": "member..name@example.com"},
    {"email": "a" * 65 + "@example.com"},
    {"password": "short"},
    {"password": "p" * 201},
])
def test_registration_rejects_invalid_and_privileged_input(auth_client, invalid):
    client, sessions = auth_client
    response = client.post("/api/auth/register", json={**NEW_ACCOUNT, **invalid})
    assert response.status_code == 422, response.text
    with sessions() as db:
        assert db.query(User).count() == 3
        assert db.query(Workspace).count() == 0


def test_registration_duplicate_does_not_overwrite_account(auth_client):
    client, sessions = auth_client
    response = client.post("/api/auth/register", json={**NEW_ACCOUNT, "email": "  ADMIN@MCCIA.ORG  "})
    assert response.status_code == 409
    assert "set-cookie" not in response.headers
    with sessions() as db:
        admin = db.query(User).filter_by(email="admin@mccia.org").one()
        assert admin.name == "Admin"
        assert admin.role == "Admin"
        assert verify_password("Mccia@2026!", admin.password_hash)
        assert db.query(User).count() == 3
        assert db.query(Workspace).count() == 0
        assert db.query(LoginSession).count() == 0


def test_registration_origin_and_rate_limit(auth_client):
    client, sessions = auth_client
    assert client.post("/api/auth/register", json=NEW_ACCOUNT, headers={"Origin": "https://untrusted.example"}).status_code == 403
    for _ in range(10):
        assert client.post("/api/auth/register", json={**NEW_ACCOUNT, "email": "admin@mccia.org"}).status_code == 409
    assert client.post("/api/auth/register", json=NEW_ACCOUNT).status_code == 429
    with sessions() as db:
        assert db.query(User).count() == 3


def test_registration_rolls_back_if_session_creation_fails(auth_client, monkeypatch):
    _, sessions = auth_client

    def fail_session(*_args):
        raise RuntimeError("Simulated session storage failure")

    monkeypatch.setattr("app.main.create_session", fail_session)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.post("/api/auth/register", json=NEW_ACCOUNT)
        assert response.status_code == 500
        assert "set-cookie" not in response.headers
        with sessions() as db:
            assert db.query(User).count() == 3
            assert db.query(Workspace).count() == 0
            assert db.query(Membership).count() == 0
            assert db.query(LoginSession).count() == 0
    finally:
        client.close()
