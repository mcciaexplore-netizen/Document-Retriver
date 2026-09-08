# MCCIA Enterprise Document Search

Private enterprise search, evidence retrieval, and audit for MSMEs and MCCIA teams. Upload business files, search their contents, and inspect the precise sheet, cell, page, or slide behind a result. All document processing and search run inside the deployed application; there are no external model services, embeddings, chatbots, or generated answers.

The project lives directly in **Doc-retriver/**.

For hosted deployment, see **[DEPLOYMENT.md](DEPLOYMENT.md)**. In Vercel select **`.` (repository root)** as the Root Directory and set `BACKEND_URL` to your deployed backend origin. The optional root `render.yaml` configures a persistent backend service.

## Start with Docker

Install Docker Desktop with Docker Compose, then run from this folder:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open **http://localhost:3000**. API documentation is available at **http://localhost:8000/docs**. Compose waits for PostgreSQL and the backend to become healthy before starting their dependent services. Database migrations run before the backend starts, and the initial launch creates the configured administrator and optional demonstration data.

The following accounts are available when `DEMO_SEED=true` (the default):

| Role | Email | Initial password |
| --- | --- | --- |
| Admin | `admin@mccia.org` | `Mccia@2026!` |
| Manager | `manager@mccia.org` | `Manager@2026!` |
| Viewer | `viewer@mccia.org` | `Viewer@2026!` |

The login page includes **Create account**. Enter your name, email, password (at least 10 characters), and password confirmation to create a saved account and sign in immediately. Registration gives you the Manager role and a new private workspace. An administrator can assign access to an existing shared workspace in **Workspaces**.

You can also select **Admin**, **Manager**, or **Viewer** under **Try the local demo**. These buttons use the regular password/session login and appear only while demo mode is enabled and the matching account still has its original demo credentials. Custom credentials are never returned by the public login-options API.

These credentials are for the local proof of concept. Set the password variables in `.env` before the first enterprise deployment. Bootstrap settings create initial users; changing them later does not automatically change existing passwords. Set `ALLOW_REGISTRATION=false` to require administrator-managed accounts. When unset, registration follows `DEMO_SEED`, so disabling demo mode also disables registration by default.

To stop the containers, run `docker compose down`. PostgreSQL data and uploaded originals persist in the `postgres_data` and `document_storage` named volumes. A restart does not erase them. The database is reachable only inside the Compose network; the browser and API ports bind to the local machine by default.

## Run locally on Windows

After setup, double-click **start.cmd**, or run `.\start.cmd` from this folder. It loads `.env`, migrates the database, starts the backend and frontend, and verifies the document API through the frontend before displaying **App ready**. It works without changing PowerShell's script execution policy. Keep its terminal open; Ctrl+C stops the services it started. You can also run `.\.venv\Scripts\python.exe scripts/start.py` directly.

Requirements: Node.js 22 LTS or later and Python 3.12. PostgreSQL is optional for local development; the default is SQLite with a local full-text index.

```powershell
.\scripts\setup.ps1
```

If Python is not on your PATH, pass its full path: `.\scripts\setup.ps1 -Python 'C:\path\to\python.exe'`. If this workspace already has `.tools\uv.exe`, setup can use its managed Python installation instead. Dependency installation needs network access the first time.

If startup reports `uv trampoline failed to spawn Python child process` or `An Application Control policy has blocked this file`, Windows is preventing the local Python runtime from running. Install a Python 3.12+ runtime approved for your machine (or ask your administrator to approve it), then run `.\scripts\setup.ps1 -Python 'C:\path\to\python.exe'` with its actual path. Passing `-Python` now refreshes an existing virtual environment as well as creating a new one. Existing documents and the database are preserved.

If `/api/health` returns another service's response, choose a free `BACKEND_PORT` in the root `.env` and set `BACKEND_URL=http://127.0.0.1:<that port>`. Restart both services using the scripts below so they load the same configuration. The frontend launch script also derives `BACKEND_URL` from `BACKEND_PORT` when no URL is set.

Start the services in two terminals:

```powershell
# Terminal 1, from Doc-retriver
.\scripts\start-backend.ps1
```

```powershell
# Terminal 2, from Doc-retriver
.\scripts\start-frontend.ps1
```

Then open **http://localhost:3000**. The scripts load the root `.env` without evaluating it as code. Backend data defaults to `mccia.db`; original documents are stored in `storage/`. Press Ctrl+C in each terminal to stop it.

If PowerShell blocks local scripts, use the equivalent commands below or start a task-specific PowerShell process with an execution policy permitted by your organization.

## Manual local setup (macOS, Linux, or Windows)

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell instead:
# .\.venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
npm ci

python -m alembic upgrade head
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, run `npm run dev` from the project root. Manual commands use backend defaults; export environment variables into the process when overriding them. On macOS/Linux, use `python3` if `python` is not available. Do not commit private uploads, local databases, or `.env`; they are excluded by `.gitignore`.

## Product workflow

1. Sign in or choose **Create account** to register your own email and create a private workspace. Administrators can create and manage shared workspaces.
2. Open **Upload / Sync** or **Files** and upload XLSX, CSV, PDF, or PPTX files. Multiple files and browser folder selection are supported.
3. The backend validates each file, saves the original, creates a processing job, extracts records, and builds the index. Files show indexed or failed status with a readable error when processing fails. Duplicate uploads are detected within the workspace.
4. Open **Enterprise Search**, enter keywords, and narrow the results using the filter panel. Each result includes its relevance score, source details, and citation.
5. Select **Open Source** to inspect neighboring spreadsheet rows, the PDF page, or the extracted slide. Export matching evidence as CSV when needed.
6. Review **Audit** to trace searches, source opens, uploads, re-indexing, exports, and deletion events.

Dashboard figures and activity are computed from database records. The evidence summary is a projection of matching structured records, including the primary result and its citation.

## Architecture

```text
Browser
  │ same-origin HTTP + session cookie
  ▼
Next.js frontend :3000
  │ /api/* proxy
  ▼
FastAPI backend :8000
  ├── SQLAlchemy → PostgreSQL (Docker) / SQLite (local)
  ├── File validation → local original-file storage
  ├── Format parsers → structured records → full-text index
  ├── Deterministic filtering, matching, and relevance scoring
  └── Sessions, workspace authorization, search history, audit events
```

```text
Doc-retriver/
  app/                  Next.js pages and layout (Vercel root application)
  components/           React UI components
  lib/                  Frontend API client
  public/               Static assets
  package.json          Frontend dependencies and npm commands
  vercel.json           Vercel deployment configuration
  main.py               FastAPI entry point; backend modules live at root
  requirements.txt      Backend dependencies
  migrations/           Database migrations
  tests/                Backend tests
  Dockerfile.backend    Backend container build
  storage/              Local original documents (private, not committed)
  scripts/              Setup and development launch scripts
  docker-compose.yml    Frontend, backend, PostgreSQL, persistent volumes
  .env.example          Documented configuration defaults
```

No business file content is sent to an external search or inference service. Package/image downloads are needed to build an installation; a prebuilt deployment can run without outbound access. Local storage is isolated by server-generated identifiers so a future storage adapter can target MinIO, S3, Azure Blob, or an internal NAS.

## Parsing and source citations

| Format | Indexed content | Citation and source inspection |
| --- | --- | --- |
| XLSX | Sheets, row context, headers, cell values, formulas, merged-range metadata | File → sheet → row → cell; surrounding rows and matched-cell highlighting |
| CSV | Decoded tabular rows, headers, and values | File → row → column; row context with matching value |
| PDF | Text extracted by page and paragraph/block | File → page → block; original PDF page and extracted text |
| PPTX | Slide titles, text blocks, tables, and available notes | File → slide → text block; extracted slide context |

Parsers normalize content into a common searchable record while preserving coordinates and format-specific metadata. Originals remain downloadable through authenticated endpoints.

Spreadsheet formulas are preserved, but the application does not calculate formulas. Cached values depend on whether the workbook was saved by an application that calculates them; when no cached value is available, the formula expression is displayed. Image-only/scanned PDFs require OCR before upload; no OCR engine is included. Complex PDF table layout and presentation rendering may be represented as extracted text rather than pixel-perfect reconstructed tables or slides. Browser folder imports upload a snapshot; they cannot watch the local filesystem continuously.

The initial parser limits are 100,000 searchable records per document, 50,000 rows / 500 columns per spreadsheet sheet or CSV, 2,000 PDF pages or presentation slides, and 200 MB of expanded Office archive data. An upload batch accepts up to 30 files. These bounds protect a single-process installation from unexpectedly large documents; failures are recorded against the file and its processing job.

## Search and indexing

Search operates only within workspaces accessible to the signed-in user. PostgreSQL provides the production full-text index; local SQLite uses FTS5. Structured metadata supports exact document, sheet, page, slide, numeric, date, type, and source constraints alongside textual matching.

Queries support keywords, quoted phrases, explicit `AND`, `OR`, and `NOT`, exact identifiers such as `PO-1023`, and numeric comparisons. Matching terms are highlighted as text rather than injected HTML. Results retain their location even when the query matches surrounding row context.

Examples to try with the seeded files:

```text
total spending west
"approved supplier"
PO-1023
machine maintenance
contract expiry
```

Queries combine uppercase `AND`, `OR`, and `NOT`, parentheses, and implicit `AND` between keywords. Numeric comparison phrases include `above`, `below`, `over`, `under`, `at least`, and `at most` followed by a number. Filter fields provide exact coordinate and numeric constraints; this is a small deterministic grammar, not natural-language interpretation.

Ranking uses `0.35 × phrase match + 0.25 × keyword match + 0.15 × header match + 0.10 × filename match + 0.10 × location match + 0.05 × recency`. Recency decreases linearly over 365 days. Relevance measures lexical evidence, not an inferred business answer.

The Finance demonstration workspace contains `spending_report.xlsx`, `approved_suppliers.csv`, `compliance_register.pdf`, and `operations_review.pptx`. The seeded spreadsheets include the West Region spending example and purchase order `PO-1023`; Procurement, Compliance, and Operations workspaces are also available.

## API

FastAPI's interactive OpenAPI specification at `http://localhost:8000/docs` lists all current endpoints and request schemas. The API is also available through the frontend at `/api`.

Principal API areas:

| Area | Purpose |
| --- | --- |
| `/api/auth/*` | Registration, login options, login, current session, password change, and logout |
| `/api/users` | Administrator-managed user listing and creation |
| `/api/workspaces` | Authorized workspace listing and management |
| `/api/files` | File listing and management |
| `/api/files/upload` | Multipart upload and indexing |
| `/api/files/{id}/download` | Authenticated original-file download |
| `/api/files/{id}/reindex` | Start a new processing job |
| `/api/search` | Ranked evidence retrieval with filters |
| `/api/search/export` | CSV export using the same search body |
| `/api/search/history` | Recent searches for a workspace |
| `/api/records/{id}/source` | Source context for an evidence record |
| `/api/dashboard` | Workspace statistics and activity |
| `/api/audit` | Authorized audit event listing |
| `/api/settings` | Application configuration |
| `/api/health` | Public service/database health probe |

Example search body:

```json
{
  "query": "total spending west",
  "workspace_id": 1,
  "filters": { "file_type": "xlsx" }
}
```

Search results include structured `file`, `location`, and citation fields, a score, and the matching text or value. Export includes the top returned matches, capped by `SEARCH_RESULT_LIMIT` (100 by default); `X-Exported-Results` and `X-Total-Results` report the exported and overall counts. Narrow the filters to export a more focused set.

File upload uses multipart fields `workspace_id`, repeated `files`, and optional `duplicate` (`skip` or `replace`), `source_type` (`upload` or `local_folder`), `category`, and `last_modified` (a JSON array of ISO timestamps or browser millisecond timestamps in file order). It returns HTTP 202 with accepted files, skipped duplicates, and per-file errors. Poll `/api/files?workspace_id=...` for processing status while the background tasks run. Authenticated requests require the HTTP-only session cookie returned by login. Direct clients should retain cookies between requests.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./mccia.db` locally | SQLAlchemy database URL; Compose supplies PostgreSQL |
| `STORAGE_PATH` | Project-root `storage/` locally | Directory for original uploaded files |
| `POSTGRES_DB` / `POSTGRES_USER` | `mccia` | Compose PostgreSQL bootstrap settings |
| `POSTGRES_PASSWORD` | `mccia_local_dev` | Compose PostgreSQL password; use URL-safe characters or URL-encode in a custom database URL |
| `FRONTEND_PORT` / `BACKEND_PORT` | `3000` / `8000` | Local published ports |
| `BACKEND_URL` | `http://127.0.0.1:8000` locally | Next.js API proxy target; Docker build sets `http://backend:8000` |
| `ADMIN_EMAIL` | `admin@mccia.org` | Initial administrator email |
| `ADMIN_PASSWORD` | `Mccia@2026!` | Initial administrator password |
| `MANAGER_PASSWORD` / `VIEWER_PASSWORD` | Demo passwords above | Optional demo account passwords |
| `DEMO_SEED` | `true` | Create sample workspaces, accounts, and documents on first boot |
| `ALLOW_REGISTRATION` | Follows `DEMO_SEED` when unset | Enable account creation with an isolated private workspace |
| `COOKIE_SECURE` | `false` | Restrict session cookies to HTTPS when true |
| `SESSION_HOURS` | `12` | Session lifetime |
| `CORS_ORIGINS` | Local frontend origins | Comma-separated allowed browser origins |
| `MAX_UPLOAD_MB` | `25` | Per-file upload limit |
| `SEARCH_RESULT_LIMIT` | `100` | Maximum returned evidence records |
| `AUDIT_RETENTION_DAYS` | `365` | Displayed retention policy; automatic purge is not implemented |

Next.js rewrite destinations are fixed during a production build. Rebuild the frontend if you change the backend proxy hostname. For nondefault frontend ports, update `CORS_ORIGINS` as appropriate.

## Access and deployment notes

Passwords use salted scrypt hashing. Sessions use random tokens whose hashes are stored server-side; cookies are HTTP-only. File endpoints require authentication, and workspace membership is checked by the backend. Admins manage workspaces and delete files; managers can upload, re-index, search, and access audit activity; viewers can search, inspect sources, and download permitted originals. Demo managers and viewers are members of the seeded workspaces. Newly created workspaces require an administrator to grant membership before other users can access them. Upload validation includes extension/content checks, size limits, safe storage names, and workspace-level duplicate handling. Queries are built using parameterized database operations.

For a deployment beyond localhost, place the frontend behind an HTTPS reverse proxy, set `COOKIE_SECURE=true`, configure permitted origins, choose private database credentials, disable demo seeding, and back up both database and document storage together. The single-process parsing pipeline is suitable for this proof of concept; very large file collections should use a dedicated job queue and worker pool. On restart, interrupted processing jobs are marked failed so users can explicitly re-index them. Schema changes are managed with Alembic; run `alembic upgrade head` from the project root before starting against an existing database (the provided scripts and Docker startup do this).

Google Drive and scheduled local/network folder synchronization are documented integration placeholders. They are shown transparently in Data Sources and do not imply an active connection. Folder selection provides immediate file import. An air-gapped installation requires that Python packages, Node packages, and Docker images be supplied beforehand.

The [official MCCIA logo](https://www.mcciapune.com/static/assets/images/logos/logo-mccia-white-blue-new.png), discovered on the MCCIA website, is bundled locally at `public/mccia-logo.png`. The application does not need an external image request to display its branding.

## Verification

```powershell
# Backend functional tests (from Doc-retriver, after setup)
.\.venv\Scripts\python.exe -m pytest tests -q

# Frontend type checking and production build
npm run build

# Running application: all four formats through the frontend API proxy
.\.venv\Scripts\python.exe scripts/smoke_test.py --url http://localhost:3000
```

The HTTP smoke script creates real XLSX, CSV, PDF, and PPTX fixtures in a temporary workspace, checks precise search citations, opens sources, downloads originals, exports results, verifies audit history, and deletes only its own workspace. It also checks unauthorized requests and session logout. Override `--email` or use `ADMIN_EMAIL` / `ADMIN_PASSWORD` environment variables for a customized administrator account.

Use a viewer account to verify restricted actions are unavailable. A Docker build should be checked separately on a machine with Docker available; local SQLite verification does not substitute for PostgreSQL/container validation.

Local verification completed: all 31 backend tests pass, the Next.js production build and TypeScript checks pass, and the four-format HTTP smoke test passes both against the backend and through the frontend proxy. Registration, saved sessions, logout, repeat login, duplicate rejection, and workspace isolation were also verified against the running frontend. Tests include password changes, workspace isolation, source alignment, stale citation rejection after re-indexing, and registration transaction rollback. Docker and browser automation were unavailable in the build environment, so container/PostgreSQL execution and browser visual interaction checks have not been verified here.

Evidence responses contain a `record_version`. The source viewer sends this version to the source API; outdated results return a readable conflict instead of resolving to a changed record. Re-run the search after re-indexing to obtain fresh citations.
