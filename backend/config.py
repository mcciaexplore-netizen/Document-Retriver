import os
from pathlib import Path
from sqlalchemy.engine import URL


# Keep existing local databases and uploads at the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def normalize_database_url(value: str) -> str:
    # Hosting providers commonly supply these aliases; we install psycopg v3.
    for prefix in ("postgres://", "postgresql://"):
        if value.startswith(prefix):
            return "postgresql+psycopg://" + value[len(prefix):]
    return value


def database_url() -> str:
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        return normalize_database_url(explicit_url)
    postgres_host = os.getenv("POSTGRES_HOST")
    if postgres_host:
        # URL.create escapes reserved characters in credentials supplied by Compose.
        return URL.create(
            "postgresql+psycopg",
            username=os.getenv("POSTGRES_USER", "mccia"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            host=postgres_host,
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "mccia"),
        ).render_as_string(hide_password=False)
    return "sqlite:///" + (PROJECT_ROOT / "mccia.db").as_posix()


DATABASE_URL = database_url()
STORAGE_PATH = Path(os.getenv("STORAGE_PATH", str(PROJECT_ROOT / "storage"))).resolve()
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "3000")
CORS_ORIGINS = [s.strip().rstrip("/") for s in (os.getenv("CORS_ORIGINS") or f"http://localhost:{FRONTEND_PORT},http://127.0.0.1:{FRONTEND_PORT}").split(",") if s.strip()]
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
SEARCH_RESULT_LIMIT = int(os.getenv("SEARCH_RESULT_LIMIT", "100"))
AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "365"))
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "12"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
DEMO_SEED = os.getenv("DEMO_SEED", "true").lower() == "true"
ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "true" if DEMO_SEED else "false").lower() == "true"
ALLOWED_TYPES = {"xlsx", "csv", "pdf", "pptx"}
