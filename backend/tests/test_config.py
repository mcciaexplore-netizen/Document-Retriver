from sqlalchemy.engine import make_url

from config import database_url


def test_postgres_password_is_encoded(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "postgres")
    monkeypatch.setenv("POSTGRES_DB", "mccia")
    monkeypatch.setenv("POSTGRES_USER", "mccia")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss:/#%?")

    url = make_url(database_url())
    assert url.drivername == "postgresql+psycopg"
    assert url.host == "postgres"
    assert url.database == "mccia"
    assert url.password == "p@ss:/#%?"


def test_explicit_database_url_takes_precedence(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://external:secret@db.example/search")
    monkeypatch.setenv("POSTGRES_HOST", "postgres")

    assert database_url() == "postgresql+psycopg://external:secret@db.example/search"
