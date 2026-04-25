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
- PostgreSQL 16 via Homebrew, user `labsmith`, database `labsmith`
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
- **Pages**:
  - `/` — Landing page (redirects to dashboard if signed in)
  - `/sign-in`, `/sign-up` — Clerk components
  - `/dashboard/labs` — Authenticated dashboard with user profile card
- **Dashboard layout**: sidebar (nav) + topbar (UserButton) + main content area
- **API client** (`src/lib/api.ts`): `apiFetch<T>()` with Clerk token injection
- **shadcn/ui components**: Button, Card, Avatar, Separator

#### Tests
- **17 tests passing** — 13 original CAD pipeline tests + 4 new app tests
- `test_app.py` verifies legacy routes work through new main.py and auth returns 401 without token

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
      layout.tsx          # ClerkProvider + fonts
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
# 1. Start PostgreSQL
brew services start postgresql@16

# 2. Run migration (first time only)
cd backend && python3 -m alembic upgrade head && cd ..

# 3. Start backend (port 8000)
npm run backend:dev

# 4. Start frontend (port 3000)
npm run frontend:dev

# 5. Run tests
npm run backend:test
```

### Environment Setup

**backend/.env** requires:
```
LABSMITH_DATABASE_URL=postgresql+asyncpg://labsmith:labsmith@localhost:5432/labsmith
LABSMITH_CLERK_SECRET_KEY=sk_test_...
LABSMITH_CLERK_PUBLISHABLE_KEY=pk_test_...
LABSMITH_CLERK_JWKS_URL=https://<instance>.clerk.accounts.dev/.well-known/jwks.json
```

**frontend/.env.local** requires:
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

---

## Milestone 2: Labs + Projects + Sessions CRUD — NEXT

### What needs to be built

#### Backend
- **Labs CRUD**: `POST/GET /api/v1/labs`, `GET/PATCH/DELETE /api/v1/labs/{lab_id}`
- **Lab membership**: `GET/POST /api/v1/labs/{lab_id}/members`, `PATCH/DELETE /api/v1/labs/{lab_id}/members/{id}`
- **`require_lab_role` dependency** — authorization check (owner, admin, member, viewer) per endpoint
- **Projects CRUD**: `POST/GET /api/v1/labs/{lab_id}/projects`, `GET/PATCH/DELETE /api/v1/projects/{project_id}`
- **Sessions CRUD**: `POST/GET /api/v1/projects/{project_id}/sessions`, `GET/PATCH/DELETE /api/v1/sessions/{session_id}`
- Service layer for each entity (business logic separate from routes)
- Pydantic request/response schemas for all endpoints

#### Frontend
- Lab list page, create lab form, lab detail/overview page
- Lab settings page with member management (invite, change role, remove)
- Project list within a lab, create project form, project detail
- Session list within a project (session creation will be fleshed out in M3)
- Sidebar navigation with lab/project hierarchy
- Breadcrumb navigation

#### Key patterns to follow
- All DB models already exist in `app/models/` — no migrations needed
- Auth dependency `get_current_user` is ready — use it in all routes
- Create new routers: `app/routers/labs.py`, `app/routers/projects.py`, `app/routers/sessions.py`
- Create new schemas: `app/schemas/labs.py`, `app/schemas/projects.py`, `app/schemas/sessions.py`
- Lab slug should be auto-generated from lab name (slugify)
- When creating a lab, auto-create an owner membership for the creator

### Subsequent Milestones (for reference)
- **M3**: Chat-based design sessions (SSE streaming, LLM parser, message persistence)
- **M4**: 3D preview + file downloads (React Three Fiber STL viewer)
- **M5**: Real CadQuery integration (replace export stubs)
- **M6**: Polish + deployment (Docker, error handling, rate limiting)
