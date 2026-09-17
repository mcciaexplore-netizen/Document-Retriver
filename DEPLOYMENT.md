# Deployment: Vercel frontend and Render backend

The repository contains a Next.js frontend in `frontend/` and a FastAPI backend in `backend/`. Root `render.yaml` provisions the backend only. The ignored root `.env` is for local use; `.env.example` and `.env.production.example` are tracked references. Set actual deployment values in the hosting dashboards, not in a committed file.

1. Create a Render Blueprint using `render.yaml`. It builds `backend/Dockerfile.backend` on Render's free web-service plan. Supply private `ADMIN_EMAIL`, a strong `ADMIN_PASSWORD`, and `CORS_ORIGINS` when creating the service. The Blueprint disables demo seeding and self-registration and enables secure cookies. This is a test deployment: SQLite and uploaded originals are stored on the ephemeral filesystem and can disappear whenever Render spins down, restarts, or redeploys the service.
2. Import this repository into Vercel with **Root Directory `frontend`** and framework **Next.js**. Set `BACKEND_URL` to the Render service's public HTTPS origin (for example `https://your-api.onrender.com`), with no `/api` suffix. Set it before building: Vercel builds now fail if it is missing or invalid. Deploy or redeploy after setting it.
3. Set the backend's `CORS_ORIGINS` to the exact Vercel frontend HTTPS origin (for example `https://your-frontend.vercel.app`). For a custom domain, add it as another comma-separated origin. Do not include paths or a trailing slash. Never use `*` for credentialed sessions.
4. Check `/api/health` at both the Render API origin and the Vercel frontend origin. Then sign in, upload a small file, and search it. Expect that test data may disappear after the backend spins down or restarts.

The browser uses the Vercel frontend's same-origin `/api/*` proxy. `BACKEND_URL` is compiled into Next.js rewrites at build time; change it in Vercel and redeploy if the API hostname changes. `CORS_ORIGINS` is enforced by FastAPI for direct cross-origin browser requests and unsafe methods. HTTP-only session cookies are issued through the proxy.

For persistent deployment, use a paid Render service with a disk mounted at `/app/storage`, or add durable storage for both database records and uploaded originals. A managed PostgreSQL service can be configured with `DATABASE_URL`; the backend accepts `postgres://`, `postgresql://`, and `postgresql+psycopg://` URLs. Database migrations run on startup. Switching URLs does not transfer existing SQLite records, and PostgreSQL alone does not preserve uploaded files on a free web service.

For Docker on your own host, `docker compose up --build` starts frontend, backend, and PostgreSQL. Supply non-demo credentials and `CORS_ORIGINS` through the host environment before deploying beyond localhost.
