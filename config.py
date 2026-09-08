import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///" + (PROJECT_ROOT / "mccia.db").as_posix())
STORAGE_PATH = Path(os.getenv("STORAGE_PATH", str(PROJECT_ROOT / "storage"))).resolve()
CORS_ORIGINS = [s.strip() for s in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if s.strip()]
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
SEARCH_RESULT_LIMIT = int(os.getenv("SEARCH_RESULT_LIMIT", "100"))
AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "365"))
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "12"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
DEMO_SEED = os.getenv("DEMO_SEED", "true").lower() == "true"
ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "true" if DEMO_SEED else "false").lower() == "true"
ALLOWED_TYPES = {"xlsx", "csv", "pdf", "pptx"}
