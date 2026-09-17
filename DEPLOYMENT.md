# Deployment: Vercel frontend and Render backend

The repository contains a Next.js frontend in `frontend/` and a FastAPI backend in `backend/`. Root `render.yaml` provisions the backend only. The ignored root `.env` is for local use; `.env.example` and `.env.production.example` are tracked references. Set actual deployment values in the hosting dashboards, not in a committed file.

1. Create a Render Blueprint using `render.yaml`. It builds `backend/Dockerfile.backend` and keeps SQLite plus original uploads on a persistent disk at `/app/storage`. Supply private `ADMIN_EMAIL`, a strong `ADMIN_PASSWORD`, and `CORS_ORIGINS` when creating the service. The Blueprint disables demo seeding and self-registration and enables secure cookies.
2. Import this repository into Vercel with **Root Directory `frontend`** and framework **Next.js**. Set `BACKEND_URL` to the Render service's public HTTPS origin (for example `https://your-api.onrender.com`), with no `/api` suffix. Set it before building: Vercel builds now fail if it is missing or invalid. Deploy or redeploy after setting it.
3. Set the backend's `CORS_ORIGINS` to the exact Vercel frontend HTTPS origin (for example `https://your-frontend.vercel.app`). For a custom domain, add it as another comma-separated origin. Do not include paths or a trailing slash. Never use `*` for credentialed sessions.
4. Check `/api/health` at both the Render API origin and the Vercel frontend origin. Then sign in, upload a small file, search it, and reopen it after a restart to verify persistent storage.

The browser uses the Vercel frontend's same-origin `/api/*` proxy. `BACKEND_URL` is compiled into Next.js rewrites at build time; change it in Vercel and redeploy if the API hostname changes. `CORS_ORIGINS` is enforced by FastAPI for direct cross-origin browser requests and unsafe methods. HTTP-only session cookies are issued through the proxy.

For a managed PostgreSQL service, set `DATABASE_URL` in Render to its private connection URL. The backend accepts `postgres://`, `postgresql://`, and `postgresql+psycopg://` URLs. Database migrations run on startup. Switching URLs does not transfer an existing SQLite database; migrate records separately and retain original uploads in persistent `STORAGE_PATH`.

For Docker on your own host, `docker compose up --build` starts frontend, backend, and PostgreSQL. Supply non-demo credentials and `CORS_ORIGINS` through the host environment before deploying beyond localhost.
