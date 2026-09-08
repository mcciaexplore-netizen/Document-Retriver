import os
import tempfile
from pathlib import Path
os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(tempfile.gettempdir()) / 'voicelytics-tests.db').as_posix()
os.environ['JWT_SECRET'] = 'test-secret-only-012345678901234567890123456789'
os.environ['SCHEDULER_ENABLED'] = 'false'
os.environ['UPLOAD_DIR'] = str(Path(tempfile.gettempdir()) / 'voicelytics-test-uploads')
import pytest
from fastapi.testclient import TestClient
from app.database.session import Base, engine, SessionLocal
from app.seed import seed
from app.main import app, requests


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    requests.clear()
    with SessionLocal() as db:
        seed(db, 'TestingPass123!')
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def auth(client):
    def login(name='admin'):
        response = client.post('/api/auth/login', json={'email': name + '@voicelytics.local', 'password': 'TestingPass123!'})
        assert response.status_code == 200, response.text
        return {'Authorization': 'Bearer ' + response.json()['access_token']}
    return login
