# Deploy frontend and backend together

Deploy this repository as **one Render web service**, using the root `render.yaml` Blueprint. It runs the Next.js frontend and Python backend in one container with one public URL.

## Steps

1. In Render, select **New → Blueprint**.
2. Connect `mcciaexplore-netizen/Document-Retriver`, branch `main`.
3. Use the root `render.yaml` file.
4. Enter `ADMIN_EMAIL` and a strong `ADMIN_PASSWORD` privately in Render.
5. Review the paid Starter service and persistent disk cost, then deploy.
6. Once the service is healthy, open its `https://...onrender.com` URL and sign in with the administrator credentials you entered.

You do not need a Vercel project or a separate backend URL for this option. The existing Vercel frontend can remain deployed separately, but it is not part of the combined service.

## What is configured

- `Dockerfile.fullstack` builds the frontend and installs the backend dependencies.
- `serve.py` runs migrations, starts the API on internal loopback port 8000, then starts Next.js on Render's public `PORT` (10000 by default).
- Next.js forwards `/api/*` requests internally. Login cookies use the same public domain as the frontend.
- The startup script adds Render's assigned public URL to the allowed origins automatically.
- `/api/health` checks the API through the frontend, so Render only marks the service healthy when both are connected.
- SQLite lives at `/var/data/mccia.db`; uploaded files live at `/var/data/storage`. The Blueprint attaches a persistent disk at `/var/data`.
- Demo accounts are disabled. Registration is enabled; set `ALLOW_REGISTRATION=false` if administrators should create all accounts.
- If either process fails, the container exits so the hosting platform can restart it.

Keep one instance when using this SQLite configuration. Disk-backed deployments have deployment constraints and are not a zero-downtime scaling setup. Back up the database and uploaded originals. Local files and users are not transferred by Git; the hosted deployment starts with a new database.

If you add a custom domain, set `CORS_ORIGINS=https://your-domain.example` in Render. The generated Render domain remains allowed as well. Do not set the internal API port or `BACKEND_URL` for the combined container: its internal address is fixed during the frontend build.

## Existing backend-only Blueprint

Earlier revisions of `render.yaml` described a Python backend-only service. If you already created one, leave its disk and data intact and create a new Blueprint/service for this combined Docker configuration. It uses the new name `document-retriever`. Do not delete the old disk until any required data has been migrated and verified.

## Verify after deployment

1. Open `https://YOUR-SERVICE.onrender.com/api/health`; expect JSON with `status: ok` and the MCCIA service name.
2. Sign in, create a workspace, upload a small CSV or PDF, search for its contents, and open its source.
3. Sign out and sign in again.
4. Restart the service and confirm the uploaded document still exists.

The repository's `scripts/smoke_test.py --url https://YOUR-SERVICE.onrender.com` automates the four-format workflow. Run it with the backend Python environment and administrator credentials supplied privately through environment variables. It creates and cleans up its own temporary workspace.

## Other deployment options

For Vercel frontend-only deployment, use Root Directory `.`, Framework Next.js, and leave `BACKEND_URL` unset. To connect that frontend to a separately hosted API, set `BACKEND_URL` to its HTTPS origin, allow the Vercel domain in the API's `CORS_ORIGINS`, and redeploy Vercel. Vercel alone does not host this combined persistent container.

For your own Docker host, the existing `docker-compose.yml` continues to run the frontend, backend, and PostgreSQL as separate containers. The individual Dockerfiles are preserved.

References: [Render Blueprints](https://render.com/docs/infrastructure-as-code), [Docker on Render](https://render.com/docs/docker), [persistent disks](https://render.com/docs/disks), [Render environment variables](https://render.com/docs/environment-variables).
