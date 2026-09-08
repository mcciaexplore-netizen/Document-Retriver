# Deploy Document Retriever

The repository contains two services:

```text
Document-Retriver/
  package.json       Next.js application at repository root
  package-lock.json
  vercel.json        Vercel configuration
  next.config.ts
  app/               Pages and application layout
  components/        UI components
  lib/               Frontend API client
  public/            Static assets
  backend/           FastAPI application: deploy on a persistent server
    requirements.txt
    app/
  render.yaml        Optional Render backend blueprint
  scripts/           Local development tools
```

## 1. Deploy the backend

The frontend deploys from the repository root. The backend uses background document processing, a database, and local uploaded files; its current storage design needs a separate persistent server and disk.

One supported configuration is provided in `render.yaml`. In Render, create a **Blueprint**, connect this GitHub repository, and select that file. This configuration selects a **paid Starter service with a persistent disk**; review the displayed cost before deploying.

Supply the requested variables:

| Variable | Value |
| --- | --- |
| `ADMIN_EMAIL` | Your administrator email |
| `ADMIN_PASSWORD` | A strong, private initial password |
| `CORS_ORIGINS` | Your exact frontend origin, e.g. `https://document-retriever.vercel.app` |

The blueprint persists SQLite and uploads under `/var/data`, runs migrations before startup, disables demo accounts, and enables registration. Set `ALLOW_REGISTRATION=false` if only administrators should create accounts. Initial administrator settings create a user on first startup; changing these variables later does not reset its password.

Wait for the backend health check to pass. Open `https://YOUR-BACKEND.onrender.com/api/health` and confirm `status` is `ok` and `service` is `MCCIA Enterprise Document Search`. Copy the backend origin without `/api/health`.

If you already have a persistent Docker server, the existing `docker-compose.yml` is another option. The Render blueprint uses one backend instance with SQLite; do not scale it to multiple instances sharing separate local databases.

## 2. Deploy the frontend on Vercel

Import this repository, then use these settings:

| Setting | Value |
| --- | --- |
| Root Directory | **`.` (repository root)** |
| Framework Preset | **Next.js** |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | Leave the Next.js default |
| Node.js Version | **22.x** |

In the Root Directory dialog, choose the radio button beside **Document-Retriver (root)**, then Continue. The `vercel.json` file supplies the framework and commands.

If this Vercel project previously used `frontend` as its Root Directory, change it to the repository root and redeploy the latest commit. The `frontend` folder has been removed. The backend is excluded from Vercel uploads by `.vercelignore`.

Add `BACKEND_URL=https://YOUR-BACKEND.onrender.com` in Vercel's Environment Variables before deploying. Use the backend's actual public URL with no `/api` suffix. Apply it to each environment you deploy. Localhost addresses refer to Vercel's machine, not your computer.

Keep administrator passwords and database variables on the backend. Do not copy your entire local `.env` into Vercel. `FRONTEND_PORT` and `BACKEND_PORT` are local launcher settings and are unnecessary on Vercel.

## 3. Connect and verify

Once Vercel assigns the frontend domain, update the backend's `CORS_ORIGINS` to that exact `https://...` origin if it differs from the value entered earlier. Multiple trusted origins can be comma-separated. Preview deployments need their exact origins added too; do not use a wildcard for authenticated requests.

1. Open `https://YOUR-FRONTEND.vercel.app/api/health` and check for the document service's healthy response.
2. Sign in using the administrator credentials configured on the backend.
3. Create a workspace, upload a small CSV or PDF, search its contents, and open its source.
4. Sign out and sign in again to verify the session cookie.

If login returns 403, check `CORS_ORIGINS`. If the API returns 502 or a connection error, check the backend health and `BACKEND_URL`. Rebuild/redeploy Vercel after changing `BACKEND_URL`: Next.js fixes the rewrite destination during the build.

Existing local documents, users, and databases are not uploaded by Git. A new deployment starts with its own database. Hosting accounts and deployed URLs must be configured before a live deployment can be verified.

References: [Vercel monorepos](https://vercel.com/docs/monorepos), [Render blueprints](https://render.com/docs/blueprint-spec), [Render persistent disks](https://render.com/docs/disks).
