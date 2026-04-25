# LabSmith — Implementation Progress

## Milestone 1: Project Restructure + Database + Auth — COMPLETE

### What was done

#### Backend Restructure
- Created `backend/app/` as the new application layer alongside the existing `backend/src/labsmith/` CAD pipeline
- **Entry point**: `backend/app/main.py` → `app.main:app` (replaces old `labsmith.main:app`)
- **Legacy routes preserved**: `/health`, `/templates`, `/parse`, `/design` all work via `app/routers/legacy.py`
- **New v1 routes**: `/api/v1/auth/me`, `/api/v1/auth/webhook`
- Global exception handler ensures all errors (including unhandled) return JSON with CORS headers
- Config via `pydantic-settings` in `app/config.py` — reads from `backend/.env` with `LABSMITH_` prefix

#### Database (PostgreSQL + SQLAlchemy async + Alembic)
- PostgreSQL 16 local dev database, user `labsmith`, database `labsmith`
- Verified Docker path: container `labsmith-postgres` exposes `localhost:5432` using the same credentials as `backend/.env.example`
- Homebrew PostgreSQL is also valid if the service is installed, running, and has the expected role/database
- Async SQLAlchemy engine in `app/database.py`
- **7 ORM models** in `app/models/`:
  - `User` (synced from Clerk — clerk_user_id, email, display_name, avatar_url)
  - `Laboratory` (name, slug, description, created_by)
  - `LabMembership` (user_id, laboratory_id, role enum: owner/admin/member/viewer, invited_by)
  - `Project` (laboratory_id, name, description, created_by)
  - `DesignSession` (project_id, title, status enum: active/completed/archived, part_type, current_spec JSONB)
  - `Message` (session_id, role enum: user/assistant/system, content, metadata JSONB)
  - `Artifact` (session_id, message_id, artifact_type enum: stl/step/spec_json/validation_json, file_path, spec_snapshot JSONB, version)
- All models use UUID primary keys, timestamptz created_at/updated_at
- Alembic configured at `backend/alembic/` with async engine
- Initial migration: `0975421fbff3_initial_schema.py` — creates all 7 tables

#### Clerk Auth
- `app/auth/clerk.py`: JWKS fetch (cached), JWT verification, `get_current_user` dependency
- JWKS URL derived from Clerk instance (set `LABSMITH_CLERK_JWKS_URL` in `.env`)
- `get_current_user` auto-upserts user from JWT claims if webhook hasn't fired yet
- `POST /api/v1/auth/webhook` handles `user.created`, `user.updated`, `user.deleted` with svix signature verification
- Proper error handling: malformed tokens → 401, JWKS unavailable → 503

#### Frontend (Next.js 16 + Clerk + shadcn/ui)
- Replaced Vite SPA with Next.js 16 + TypeScript + Tailwind CSS v4 + App Router
- `@clerk/nextjs` for auth — middleware protects all routes except `/`, `/sign-in`, `/sign-up`
- Removed `next/font/google` usage so production builds do not require fetching Google Fonts; the app now uses a system font stack
- **Pages**:
  - `/` — Landing page (redirects to dashboard if signed in)
  - `/sign-in`, `/sign-up` — Clerk components
  - `/dashboard/labs` — Authenticated dashboard with user profile card
- **Dashboard layout**: sidebar (nav) + topbar (UserButton) + main content area
- **API client** (`src/lib/api.ts`): `apiFetch<T>()` with Clerk token injection, API base URL validation, and readable errors when a request accidentally returns HTML
- **shadcn/ui components**: Button, Card, Avatar, Separator

#### Tests
- **17 tests passing** — 13 original CAD pipeline tests + 4 new app tests
- `test_app.py` verifies legacy routes work through new main.py and auth returns 401 without token
- Frontend checks verified with `npm --prefix frontend run lint` and `npm --prefix frontend run build`

#### Repo Hygiene
- Root `.gitignore` covers Python caches, coverage output, local env files, virtualenvs, `node_modules`, Next/Vite build output, Turbo/Vercel caches, generated CAD output, Claude local files, and logs
- `backend/.env` and `frontend/.env.local` are intentionally ignored
- `backend/.env.example` and `frontend/.env.local.example` are safe templates and should stay tracked
- `frontend/dist/` may exist from the earlier Vite scaffold but is ignored and should not be committed

### File Structure

```
backend/
  app/
    main.py              # FastAPI app — CORS, exception handler, routers
    config.py            # pydantic-settings (reads backend/.env)
    database.py          # async SQLAlchemy engine + session factory
    dependencies.py      # FastAPI dependency helpers
    auth/
      clerk.py           # JWKS fetch, JWT verify, get_current_user
    models/
      base.py            # DeclarativeBase, UUID + timestamp mixins
      user.py            # User ORM model
      laboratory.py      # Laboratory ORM model
      lab_membership.py  # LabMembership + LabRole enum
      project.py         # Project ORM model
      design_session.py  # DesignSession + SessionStatus enum
      message.py         # Message + MessageRole enum
      artifact.py        # Artifact + ArtifactType enum
    routers/
      auth.py            # GET /api/v1/auth/me, POST /api/v1/auth/webhook
      legacy.py          # /health, /templates, /parse, /design
    schemas/
      auth.py            # UserResponse pydantic model
  src/labsmith/          # Original CAD pipeline (unchanged)
    parser/              # RuleBasedParser
    templates/           # TMA mold, tube rack, gel comb
    validation/          # Part request validation rules
    export/              # Export plan (stubs — no real CAD yet)
    models.py            # Pydantic domain models (PartRequest, etc.)
  alembic/
    env.py               # Async Alembic env
    versions/
      0975421fbff3_initial_schema.py
  tests/
    test_api.py          # Legacy API tests
    test_app.py          # New app tests (legacy routes + auth 401)
    test_parser.py       # Parser unit tests
    test_templates.py    # Template registry tests
    test_validation.py   # Validation rule tests
  .env                   # LABSMITH_* env vars (not committed)
  .env.example           # Template for .env
  alembic.ini

frontend/
  src/
    middleware.ts         # Clerk route protection
    lib/
      api.ts             # API client with token injection
      utils.ts           # cn() for tailwind class merging
    app/
      layout.tsx          # ClerkProvider + root shell
      page.tsx            # Landing page
      globals.css         # Tailwind + shadcn theme variables
      sign-in/[[...sign-in]]/page.tsx
      sign-up/[[...sign-up]]/page.tsx
      (dashboard)/
        layout.tsx        # Sidebar + topbar shell
        dashboard/labs/page.tsx  # Lab list + user profile card
    components/ui/        # shadcn components (avatar, card, separator)
  .env.local              # Clerk keys + API URL (not committed)
  .env.local.example      # Template
  components.json         # shadcn/ui config

pyproject.toml            # Python deps, pytest config, ruff config
package.json              # npm workspaces, run scripts
```

### How to Run

```bash
# 1. Start PostgreSQL with Docker
docker start labsmith-postgres

# If the container does not exist yet:
docker run --name labsmith-postgres \
  -e POSTGRES_USER=labsmith \
  -e POSTGRES_PASSWORD=labsmith \
  -e POSTGRES_DB=labsmith \
  -p 5432:5432 \
  -d postgres:16

# 2. Run migration (first time only)
npm run backend:migrate

# 3. Start backend (port 8000)
npm run backend:dev

# 4. Start frontend (port 3000)
npm run frontend:dev

# 5. Run tests
npm run backend:test
```

Homebrew PostgreSQL can be used instead of Docker:

```bash
brew services start postgresql@16
```

If migrations fail with `Connect call failed ('::1', 5432)` or `Connect call failed ('127.0.0.1', 5432)`, Postgres is not listening on `localhost:5432` or the configured database is unavailable.

### Environment Setup

**backend/.env** requires:
```
LABSMITH_DATABASE_URL=postgresql+asyncpg://labsmith:labsmith@localhost:5432/labsmith
LABSMITH_CLERK_SECRET_KEY=sk_test_...
LABSMITH_CLERK_PUBLISHABLE_KEY=pk_test_...
LABSMITH_CLERK_WEBHOOK_SECRET=whsec_...
LABSMITH_CLERK_JWKS_URL=https://<instance>.clerk.accounts.dev/.well-known/jwks.json
```

**frontend/.env.local** requires:
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

`NEXT_PUBLIC_API_BASE_URL` must be exactly a full URL such as `http://localhost:8000`. A malformed value can cause the browser to call the Next.js app instead of FastAPI and render a raw HTML 404 in the dashboard.

---

## Milestone 2: Labs + Projects + Sessions CRUD — IN PROGRESS

### Completed in this milestone

#### Backend
- Added service layer under `backend/app/services/`:
  - `access.py` — lab/project/session membership lookups and role enforcement
  - `labs.py` — lab CRUD, slug generation, member management, last-owner protection
  - `projects.py` — project CRUD scoped through lab membership
  - `sessions.py` — design session CRUD scoped through project membership
- Added Pydantic schemas:
  - `app/schemas/labs.py`
  - `app/schemas/projects.py`
  - `app/schemas/sessions.py`
- Added routers and wired them into `app.main`:
  - `POST/GET /api/v1/labs`
  - `GET/PATCH/DELETE /api/v1/labs/{lab_id}`
  - `GET/POST /api/v1/labs/{lab_id}/members`
  - `PATCH/DELETE /api/v1/labs/{lab_id}/members/{membership_id}`
  - `GET/POST /api/v1/labs/{lab_id}/projects`
  - `GET/PATCH/DELETE /api/v1/projects/{project_id}`
  - `GET/POST /api/v1/projects/{project_id}/sessions`
  - `GET/PATCH/DELETE /api/v1/sessions/{session_id}`
- Role enforcement:
  - `viewer` can read lab/project/session data
  - `member` can create/update projects and sessions
  - `admin` can update labs, manage members, and delete projects
  - `owner` can delete labs
- Lab creation automatically creates an owner membership for the creator
- Lab slugs are generated from lab names and de-duped with numeric suffixes

#### Frontend
- Expanded `frontend/src/lib/api.ts` with typed API methods for labs, projects, and sessions
- Replaced the `/dashboard/labs` placeholder with a working workspace:
  - profile summary
  - lab list + create form
  - project list + create form for the selected lab
  - session list + create form for the selected project
- The page now uses the authenticated Clerk token for all API calls

#### Tests
- Added `backend/tests/test_crud_api.py`
- CRUD integration coverage:
  - lab/project/session create, list, update, delete flow
  - viewer read access but no project creation or lab update
  - last owner cannot be demoted or removed
- Full backend suite: **20 tests passing**
- Frontend lint and production build pass

### Still to do in this milestone

#### Backend
- Add stricter permission edge cases if needed, especially around admin managing owners
- Decide whether member/project/session deletes should be admin-only or creator/member scoped
- Add pagination/search once real data volume justifies it
- Add pending invitation flow if labs need invites for users who do not yet exist

#### Frontend
- Add dedicated lab detail/settings pages
- Add member management UI
- Add project detail pages
- Add session detail page as the entry point for chat/design work in M3
- Add sidebar lab/project hierarchy
- Add breadcrumbs

### Subsequent Milestones
- **M3**: Chat-based design sessions (SSE streaming, LLM parser, message persistence)
- **M4**: 3D preview + file downloads (React Three Fiber STL viewer)
- **M5**: Real CadQuery integration (replace export stubs)
- **M6**: Polish + deployment (Docker, error handling, rate limiting)
