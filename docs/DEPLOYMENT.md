# Deployment

End-to-end deployment of LabSmith for a real users-and-data demo. The split:

| Piece                 | Host    | Why                                                                                  |
| --------------------- | ------- | ------------------------------------------------------------------------------------ |
| Next.js frontend      | Vercel  | Native Next.js + Clerk support, branch previews, free tier covers a demo             |
| FastAPI backend       | Render  | Linux x86_64 (only platform with CadQuery wheels), Docker support, persistent disks  |
| Postgres              | Render  | Managed, lives next to the backend service, free tier for the demo                   |
| Artifact / doc bytes  | Render Disk | `LocalFilesystemStorage` keeps working — swap to S3 only when needed             |

Approximate cost on the always-on tier: ~**$24/mo** (Render Standard backend $7 + Render Postgres Starter $7 + 10 GB disk $10; Vercel Hobby is free).

> **Heads-up:** the Render *Free* tier sleeps services after 15 min of inactivity and the Postgres free instance expires after 90 days. For anything you care about, jump straight to Starter on both.

---

## 0. Prerequisites

- A **Clerk** application (production instance) — grab the publishable key, secret key, JWKS URL, and a webhook signing secret.
- An **OpenAI API key** if you want the live LLM/embedding paths (`LABSMITH_CHAT_LLM_PROVIDER=openai`, `LABSMITH_SPEC_EXTRACTOR=openai`, `LABSMITH_ONBOARDING_RETRIEVER=openai`). Skip it and the backend silently falls back to mock + lexical.
- A **Render** account and a **Vercel** account.
- A custom domain is optional; instructions below use the default `*.onrender.com` and `*.vercel.app` hosts.

---

## 1. Provision Postgres on Render

1. **New → PostgreSQL**
2. Name: `labsmith-db`. Region: pick one close to where your users sit (e.g. `Oregon`). Plan: **Starter** ($7/mo).
3. Database name: `labsmith`. User: `labsmith` (Render generates a password).
4. After provisioning, copy the **Internal Database URL** — it looks like:
   ```
   postgresql://labsmith:<password>@dpg-xxxxxxxx-a/labsmith
   ```
5. Convert it to the SQLAlchemy async form by swapping the driver:
   ```
   postgresql+asyncpg://labsmith:<password>@dpg-xxxxxxxx-a/labsmith
   ```
   That string goes into `LABSMITH_DATABASE_URL` on the backend service in step 2.

---

## 2. Deploy the backend on Render

The repo already ships with `backend/Dockerfile` (Python 3.12-slim + system libs CadQuery needs).

1. **New → Web Service** → connect this GitHub repo.
2. Settings:
   - Name: `labsmith-api`
   - Region: same as the database (cross-region traffic is slow)
   - Branch: `main`
   - Root directory: leave blank (Dockerfile is at `backend/Dockerfile` — see "Dockerfile path" below)
   - Runtime: **Docker**
   - Dockerfile path: `backend/Dockerfile`
   - Docker context: `.` (repo root — the Dockerfile copies `pyproject.toml` and `backend/`)
   - Plan: **Starter** ($7/mo) so the service doesn't sleep
3. **Add a persistent disk** (required for `LABSMITH_STORAGE_BACKEND=local`):
   - Name: `labsmith-storage`
   - Mount path: `/data/storage`
   - Size: 10 GB ($10/mo) — easy to grow later
4. **Environment variables** (Settings → Environment):

   | Key                                       | Value                                                                       |
   | ----------------------------------------- | --------------------------------------------------------------------------- |
   | `LABSMITH_DATABASE_URL`                   | the `postgresql+asyncpg://...` URL from step 1.5                            |
   | `LABSMITH_CLERK_SECRET_KEY`               | `sk_live_...` from Clerk → API Keys                                         |
   | `LABSMITH_CLERK_PUBLISHABLE_KEY`          | `pk_live_...` (also goes to the frontend, fine to share)                    |
   | `LABSMITH_CLERK_WEBHOOK_SECRET`           | `whsec_...` from the webhook you create in step 4                           |
   | `LABSMITH_CLERK_JWKS_URL`                 | `https://<your-instance>.clerk.accounts.dev/.well-known/jwks.json`          |
   | `LABSMITH_CORS_ORIGINS`                   | `["https://<your-vercel-domain>"]` — JSON array, no trailing slash          |
   | `LABSMITH_STORAGE_BACKEND`                | `local`                                                                     |
   | `LABSMITH_STORAGE_DIR`                    | `/data/storage` (matches the disk mount above)                              |
   | `LABSMITH_CHAT_LLM_PROVIDER`              | `mock` for the demo, `openai` once you've added the key                     |
   | `LABSMITH_SPEC_EXTRACTOR`                 | `rule_based` or `openai`                                                    |
   | `LABSMITH_ONBOARDING_RETRIEVER`           | `lexical` or `openai`                                                       |
   | `LABSMITH_OPENAI_API_KEY`                 | `sk-...` (only required if any of the three above is set to `openai`)       |
   | `LABSMITH_DEBUG`                          | `false`                                                                     |

5. **Deploy**. First boot takes 6–10 min because CadQuery's native deps compile. After it's up, hit `https://labsmith-api.onrender.com/health` — you should see `{"status":"ok"}`.

6. **Run the initial migration.** Open the Render service shell and run:
   ```bash
   alembic -c backend/alembic.ini upgrade head
   ```
   For future deploys, either run this manually after each schema change or add it as a Render **pre-deploy command** (Settings → Build & Deploy).

---

## 3. Deploy the frontend on Vercel

1. **Add New… → Project** → import the repo.
2. Settings:
   - Framework preset: **Next.js**
   - Root directory: `frontend`
   - Build command: leave default (`next build`)
   - Output directory: leave default
   - Node version: 22
3. **Environment variables** (Project Settings → Environment Variables — set for *Production* and *Preview*):

   | Key                                  | Value                                                              |
   | ------------------------------------ | ------------------------------------------------------------------ |
   | `NEXT_PUBLIC_API_BASE_URL`           | `https://labsmith-api.onrender.com`                                |
   | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`  | `pk_live_...`                                                      |
   | `CLERK_SECRET_KEY`                   | `sk_live_...`                                                      |
   | `NEXT_PUBLIC_CLERK_SIGN_IN_URL`      | `/sign-in`                                                         |
   | `NEXT_PUBLIC_CLERK_SIGN_UP_URL`      | `/sign-up`                                                         |
   | `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL`| `/dashboard/labs`                                                  |
   | `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL`| `/dashboard/labs`                                                  |

4. **Deploy**. Visit the assigned `*.vercel.app` URL — you should see the landing page.

---

## 4. Wire up the Clerk webhook

The backend syncs Clerk users into Postgres via `POST /api/v1/auth/webhook`. Configure Clerk to call it:

1. Clerk dashboard → **Webhooks** → **Add endpoint**.
2. Endpoint URL: `https://labsmith-api.onrender.com/api/v1/auth/webhook`
3. Subscribe to: `user.created`, `user.updated`, `user.deleted`.
4. Copy the **Signing secret** (`whsec_...`) and put it into Render as `LABSMITH_CLERK_WEBHOOK_SECRET` (step 2.4 above). Save and let the backend re-deploy.
5. Hit "Send example" from the Clerk dashboard — you should see a 200 in the Render logs and a row appear in `users`.

---

## 5. Update CORS + Clerk allowed origins

Two places to update once you know the Vercel URL:

- **Render → backend env**: set `LABSMITH_CORS_ORIGINS` to a JSON array containing exactly your frontend origin(s), e.g. `["https://labsmith.vercel.app","https://labsmith-git-main-akim.vercel.app"]`. No trailing slashes. Re-deploy.
- **Clerk → Domains**: add your Vercel domain so Clerk's middleware accepts it.

---

## 6. Smoke test

From a clean browser session:

1. Visit the Vercel URL → landing page renders.
2. **Sign up** with a real email → Clerk completes → you land on `/dashboard/labs`.
3. Create a lab, create a project, create a **design session**, send a message — the agent replies and an STL appears in the viewer.
4. Create an **onboarding session**, upload a sample SOP from `docs/sample_lab_documents/`, ask a question — the agent answers with a citation.
5. In Render → the database, confirm rows exist in `users`, `laboratories`, `design_sessions`, `messages`, `artifacts`, `lab_documents`.
6. SSH into the Render service, `ls /data/storage` — STL bytes and uploaded docs should be there.

---

## 7. Operational notes

- **Logs**: `render logs labsmith-api -f` (CLI) or the dashboard tail.
- **Manual migrations**: `render ssh labsmith-api` then `alembic -c backend/alembic.ini upgrade head`.
- **Backups**: Render Postgres Starter includes daily backups with 7-day retention. Bump the plan if you need more.
- **Rate limit**: the in-process limiter (`LABSMITH_CHAT_RATE_LIMIT_REQUESTS=30/min`) is fine for a single-instance demo. Move to Redis before scaling horizontally.
- **Disk**: when `/data/storage` fills up, raise the disk size in Render (no downtime) **or** switch `LABSMITH_STORAGE_BACKEND` to `s3` once that backend is implemented.
- **Sleep prevention**: Starter plan never sleeps. If you keep services on Free, expect 30–60s cold starts on the first request after idle.

---

## 8. When to migrate off these defaults

| Trigger                                                       | What to change                                                                  |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `/data/storage` past 50 GB or you want CDN-fronted downloads  | Implement the `s3` backend in `app/services/storage.py`, set `LABSMITH_STORAGE_BACKEND=s3` |
| Multiple backend instances behind a load balancer             | Move the chat rate limiter to Redis; pin SSE connections via sticky sessions    |
| Embedding bills hurt or onboarding latency matters            | Persist embeddings in Postgres via `pgvector`, cache by `(doc_id, model)`       |
| Clerk JWKS round-trips dominate request latency               | Add a 1-hour in-process JWKS cache in `app/auth/clerk.py`                       |
| You need region failover                                      | Promote to Render Pro plan + multi-region read replicas, or migrate to Fly.io   |
