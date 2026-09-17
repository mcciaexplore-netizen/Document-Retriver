# MCCIA Enterprise Document Search

A Next.js frontend and FastAPI backend for private document upload, indexing, search, source citations, and audit history. It supports XLSX, CSV, PDF, and PPTX. Search is deterministic and does not call an external AI service.

## Layout

| Path | Purpose |
| --- | --- |
| `frontend/` | Next.js app, UI, API client, assets, npm package, and frontend Dockerfile |
| `backend/` | FastAPI routes, database models, parsers, indexing, migrations, tests, and backend Dockerfile |
| `scripts/` | Local setup and startup |
| `docker-compose.yml` | Local PostgreSQL, backend, and frontend containers |
| `render.yaml` | Backend-only Render Blueprint |

The root `mccia.db` and `storage/` are existing private application data. Do not delete them to clean the source tree. They are ignored by Git.

## Run locally on Windows

Install Node.js 22+ and Python 3.12+, then from the repository root run:

```powershell
.\scripts\setup.ps1
.\start.cmd
```

Setup installs Python dependencies into `.venv/` and Node dependencies into `frontend/node_modules/`. The launcher starts the backend on `127.0.0.1:8001` and frontend on `127.0.0.1:3000`, runs migrations, and checks `/api/health`. You can instead use `backend/scripts/start-backend.ps1` and `scripts/start-frontend.ps1` in separate terminals.

The root `.env` is the shared local configuration for the Windows launchers, direct frontend starts, and Docker Compose. It is ignored by Git. Setup creates it from the tracked `.env.example` if missing; edit `.env` to change local ports or CORS origins. Explicit process environment variables take precedence over the file. For example:

```powershell
$env:BACKEND_PORT = '8001'
$env:FRONTEND_PORT = '3000'
.\start.cmd
```

`BACKEND_URL` is the frontend's API proxy destination, not a database URL. Local launchers and direct frontend starts derive it from `BACKEND_PORT` when unset. Docker Compose supplies its internal URL. Do not put a local `DATABASE_URL` in the shared `.env`: it would override Compose's PostgreSQL connection.

For Docker, run `docker compose up --build`. Compose reads the same root `.env`, uses PostgreSQL and persistent named volumes, and has local-only defaults for its database credentials. Set private values before exposing it beyond localhost. See `.env.production.example` for hosted dashboard settings; do not deploy that file as-is.

## Configuration

| Variable | Local default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Root `mccia.db` (SQLite) | Explicit database URL; overrides Compose's PostgreSQL connection settings |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Unset / `5432` | When `POSTGRES_HOST` is set, build a PostgreSQL URL from the `POSTGRES_*` variables; Compose sets `postgres` |
| `STORAGE_PATH` | Root `storage/` | Original uploaded files |
| `BACKEND_PORT` | `8001` native / `8000` Compose | Published API port |
| `FRONTEND_PORT` | `3000` | Published Next.js port |
| `BACKEND_URL` | `http://127.0.0.1:8001` native | Next.js `/api/*` proxy destination; set before a production build |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated exact frontend origins allowed by FastAPI |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Local Compose defaults | Docker PostgreSQL bootstrap and backend connection credentials |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Demo defaults | Initial administrator; set private values before first non-demo boot |
| `MANAGER_PASSWORD`, `VIEWER_PASSWORD` | Demo defaults | Initial demo accounts only |
| `DEMO_SEED` | `true` | Populate demo users, workspaces, and sample files on a fresh database |
| `ALLOW_REGISTRATION` | Follows `DEMO_SEED` | Permit self-registration into a private workspace |
| `COOKIE_SECURE` | `false` | Set `true` for HTTPS deployment |
| `SESSION_HOURS` | `12` | Session lifetime |
| `MAX_UPLOAD_MB` | `25` | Per-file upload limit |
| `SEARCH_RESULT_LIMIT` | `100` | Maximum returned results |
| `AUDIT_RETENTION_DAYS` | `365` | Displayed policy; automatic purge is not implemented |

Bootstrap passwords affect newly created accounts only; changing a variable does not reset an existing user's password. Set `DEMO_SEED=false`, `ALLOW_REGISTRATION=false`, and a strong `ADMIN_PASSWORD` for a private production deployment. Changing `DATABASE_URL` does not transfer existing records; preserve uploaded originals in `STORAGE_PATH` too.

## CORS and API flow

The browser requests the frontend's same-origin `/api/*`. Next.js forwards those requests to FastAPI using `BACKEND_URL`, preserving the session cookie. FastAPI also enforces `CORS_ORIGINS` for direct cross-origin browser calls. Use full origins, including scheme and port, with no path or trailing slash:

```text
Local:  http://localhost:3000,http://127.0.0.1:3000
Hosted: https://your-frontend.vercel.app
```

Do not use `*` with credentialed sessions. When the frontend URL changes, update `CORS_ORIGINS` on the backend. When the backend URL changes, set `BACKEND_URL` on the frontend and rebuild it; Next.js rewrites are build-time configuration.

API documentation is at `http://127.0.0.1:8001/docs` for a native local startup. Principal endpoints include `/api/auth/*`, `/api/workspaces`, `/api/files`, `/api/files/upload`, `/api/search`, `/api/search/export`, `/api/records/{id}/source`, `/api/audit`, and `/api/health`.

## Verify

```powershell
npm.cmd run build --prefix frontend
.\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests -q
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for the separate Vercel/Render setup.
