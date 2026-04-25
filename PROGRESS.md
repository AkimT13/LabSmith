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
    middleware.ts             # Clerk route protection
    app/
      layout.tsx              # ClerkProvider + root shell
      page.tsx                # Landing page
      globals.css             # Tailwind + shadcn theme variables
      sign-in/[[...sign-in]]/page.tsx
      sign-up/[[...sign-up]]/page.tsx
      (dashboard)/
        layout.tsx            # Sidebar (HierarchySidebar) + topbar shell
        dashboard/labs/page.tsx                       # Lab/project/session workspace
        dashboard/sessions/[sessionId]/page.tsx       # Session detail shell (M3 chat lands here)
    components/
      ui/                     # shadcn (avatar, button, card, dialog, alert-dialog, separator)
      dashboard/
        hierarchy-sidebar.tsx     # Sidebar tree + "+" create-lab dialog trigger
        entity-form-dialog.tsx    # Generic name/description form (labs + projects)
        session-form-dialog.tsx   # Session create/edit form (title/part_type/status)
        confirm-delete-dialog.tsx # AlertDialog wrapper for destructive actions
    lib/
      api.ts                  # API client + types + CRUD (labs/projects/sessions)
      utils.ts                # cn() for tailwind class merging
      data-events.ts          # emitDataChanged() / useDataChangedListener()
  .env.local                  # Clerk keys + API URL (not committed)
  .env.local.example          # Template
  components.json             # shadcn/ui config

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

## Milestone 2: Labs + Projects + Sessions CRUD — COMPLETE

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
- Expanded `frontend/src/lib/api.ts` with typed API methods for labs, projects, sessions — including `update*` and `delete*` for all three.
- The `/dashboard/labs` workspace is a full CRUD UI:
  - profile summary
  - lab list (selection only — creation moved to the sidebar `+` button via dialog)
  - selected-lab header with edit/delete actions (role-gated)
  - project list with per-row edit/delete + a "New" button that opens a dialog
  - session list with per-row edit/archive/delete + a "New" button that opens a dialog
- All forms (create + edit, for labs/projects/sessions) use shared shadcn-`Dialog` components in `frontend/src/components/dashboard/`. Delete operations use `AlertDialog`-based confirmation prompts.
- Sidebar (`HierarchySidebar`) gained a `+` button for lab creation. After any mutation, components emit a `labsmith:data-changed` event (helper at `src/lib/data-events.ts`) so the sidebar tree and the workspace page refetch in sync.
- All API calls use the authenticated Clerk token via `useAuth().getToken()`.

#### Tests
- Added `backend/tests/test_crud_api.py`
- CRUD integration coverage:
  - lab/project/session create, list, update, delete flow
  - viewer read access but no project creation or lab update
  - last owner cannot be demoted or removed
- Full backend suite: **20 tests passing**
- Frontend lint and production build pass

### M2 Plan

#### M2.1 — Hierarchy Clarity + Navigation — COMPLETE
- Goal: make it obvious that projects are inside the selected lab and sessions are inside the selected project.
- Changes:
  - Add contextual headings: `Projects in {lab}` and `Sessions in {project}`
  - Add breadcrumb/context strip: `Labs / {lab} / {project}`
  - Move lab/project/session navigation into a collapsible left sidebar tree
  - Use `lab`, `project`, and `session` query params so sidebar and page selection stay in sync
  - Add empty states for "select a lab" and "select a project"
  - Update sidebar/dashboard copy to reflect the nested model
- User test:
  - Create or select a lab
  - Expand the selected lab in the left sidebar
  - Confirm the Projects panel names that lab
  - Create or select a project
  - Expand the selected project in the left sidebar
  - Confirm the Sessions panel names that project
  - Confirm sessions appear under the selected project without changing the project workspace URL
  - Refresh and confirm context restores sensibly
- Verification:
  - `npm --prefix frontend run lint`
  - `npm --prefix frontend run build`

#### M2.2 — Edit/Delete UI — COMPLETE
- Goal: expose the CRUD operations already implemented in the backend.
- Changes shipped:
  - **Sidebar lab creation**: clicking the `+` button next to "Laboratories" in the sidebar opens a dialog to create a lab. The previous inline create-lab form in the workspace content area has been removed.
  - **Lab edit/delete**: pencil + trash icons appear in the selected-lab header for users with `admin`/`owner` role. Edit opens a dialog; delete opens a confirmation alert and routes back to `/dashboard/labs` after success. Delete is owner-only; the trash icon is hidden for non-owners.
  - **Project create/edit/delete**: project list rows show pencil + trash icons (trash for `admin`/`owner` only). The "New" button at the top of the project panel opens a create-project dialog.
  - **Session create/edit/archive/delete**: session list rows show pencil + archive + trash icons. Archive uses a one-click PATCH that sets `status: archived` (icon hides once already archived). Edit opens a dialog that includes a status select. Create uses the same dialog without the status field.
  - **Cross-component refresh**: a small custom-event helper at `frontend/src/lib/data-events.ts` (`emitDataChanged()` / `useDataChangedListener()`) keeps the sidebar tree and the workspace page in sync after any mutation without a full page reload.
  - **Reusable dialogs** (`frontend/src/components/dashboard/`):
    - `entity-form-dialog.tsx` — generic name/description form (used for labs and projects). Form body is conditionally rendered when open, so initial values are picked up via `useState` initializer (no `useEffect` needed; satisfies React 19's `react-hooks/set-state-in-effect` rule).
    - `session-form-dialog.tsx` — title/part_type/optional status form (used for create + edit sessions).
    - `confirm-delete-dialog.tsx` — destructive `AlertDialog` wrapper with inline error display.
  - Added shadcn `dialog`, `alert-dialog`, and `button` components.
  - Extended `frontend/src/lib/api.ts` with `updateLab`, `deleteLab`, `updateProject`, `deleteProject`, `updateSession`, `deleteSession`.
- Permissions surfaced in UI:
  - `viewer` → no action icons
  - `member` → can create projects/sessions, edit and (where allowed) delete them
  - `admin` → can also edit lab and delete projects
  - `owner` → can also delete the lab
- User test:
  - Click `+` in sidebar → dialog opens → create a lab → sidebar refreshes
  - Edit selected lab description, save → sidebar + content reflect new name/description
  - Create a project from the "New" button in the project panel
  - Edit a project name → list updates
  - Archive a session → status badge flips to `archived` and archive icon disappears
  - Delete a session/project/lab → confirmation dialog appears, then item disappears
- Verified: `npm --prefix frontend run lint`, `npm --prefix frontend run build`, `npm run backend:test` (20 tests).

#### M2.3 — Member Management UI — COMPLETE
- Goal: make the existing lab member APIs usable from the dashboard.
- Changes shipped:
  - Added typed frontend member APIs in `frontend/src/lib/api.ts`: `fetchLabMembers`, `addLabMember`, `updateLabMember`, `removeLabMember`.
  - Added a **Lab settings** dialog in `/dashboard/labs`.
  - Member management now lives in Lab settings instead of the primary working view.
  - The settings dialog lists lab members with avatar, name/email, and role.
  - Admin users can add an existing user by email.
  - Admin users can change member roles from the list.
  - Admin users can remove members via confirmation dialog.
  - Last-owner protection is surfaced through existing backend errors in the role-change/remove flows.
  - UI role labels now match the lab operating model:
    - `admin`/`owner` -> **Admin**: PI, Post-Docs
    - `member` -> **Supervisor**: senior lab members
    - `viewer` -> **User**: visiting researchers, general lab members
  - `owner` remains an internal ownership safeguard, not a separate day-to-day lab role.
  - The dashboard primary view is now project-oriented: the lab is treated as the workspace boundary, while the main page leads with selected-project context and project/session work.
  - Added M2.4 prep APIs in `frontend/src/lib/api.ts`: `fetchLab`, `fetchProject`, `fetchSession`.
  - Removed session-as-query-param state from the project workspace; URLs now stop at `lab` and `project` until the dedicated session page lands.
  - Sidebar session rows remain visible for context but are no longer links until M2.4 creates `/dashboard/sessions/[sessionId]`.
- User test:
  - Open **Lab settings** from the selected lab workspace header
  - Confirm current user appears as `Admin`
  - Try demoting/removing the only owner and confirm the UI shows the backend error
  - If another test user exists, add them by email and change/remove role
  - Close settings and confirm the primary view returns to projects/sessions
- Verification:
  - `npm --prefix frontend run lint`
  - `npm --prefix frontend run build`
  - `npm run backend:test`

#### M2.4 — Detail Page Shells — COMPLETE (scoped down)
- Goal: prepare the route structure M3 chat/design work will live in.
- Decision: lab and project "detail" pages were skipped on purpose. The `/dashboard/labs` workspace already covers lab + project navigation well, and adding more routes for those just for the sake of routing would be churn. Only the **session detail shell** was actually needed, since M3's chat/3D viewer wants its own URL.
- Changes shipped:
  - New route at `/dashboard/sessions/[sessionId]` (file: `frontend/src/app/(dashboard)/dashboard/sessions/[sessionId]/page.tsx`).
  - Client component using `useParams()` from `next/navigation` plus the existing `fetchSession` / `fetchProject` / `fetchLab` API helpers.
  - Renders breadcrumbs (Labs / lab / project / session), a header with title + status badge + "Back to project" link, three context cards (Lab, Project, Session metadata), and a placeholder card describing what M3 will fill in.
  - Sidebar session rows are now `<Link>`s pointing at `/dashboard/sessions/[sessionId]` (previously plain text after M2.3's prep).
  - Workspace session rows: title area is now a `<Link>` to the same route. Edit/Archive/Delete icons remain inline next to the link, so quick CRUD doesn't require a navigation round-trip.
  - Detail page also subscribes to `useDataChangedListener()` so edits made elsewhere are reflected immediately.
- Why no lab/project detail routes: the workspace at `/dashboard/labs?lab=X&project=Y` already serves as the lab+project view. Adding parallel detail routes would duplicate the workspace UI. If a future need emerges (e.g., a per-lab settings page distinct from the modal), it can be added incrementally.
- User test:
  - Click a session in the sidebar → lands on `/dashboard/sessions/<id>` with breadcrumbs filled in
  - Click a session title in the workspace → same route, same content
  - "Back to project" link returns to `/dashboard/labs?lab=...&project=...` with the correct selection
  - Refresh on the session page → breadcrumbs and cards still resolve via the API
- Verified: `npm --prefix frontend run lint`, `npm --prefix frontend run build`.

#### M2.5 — Auth/Profile Polish + Final M2 Verification — COMPLETE
- Goal: remove obvious rough edges before M3.
- Changes shipped:
  - **Clerk profile mapping fix** (`backend/app/auth/clerk.py`):
    - On first user creation, `get_current_user` now calls `GET https://api.clerk.com/v1/users/{id}` (using `LABSMITH_CLERK_SECRET_KEY` as a Bearer token) to pull the real email, name, and avatar instead of relying on JWT claims that aren't in the default JWT template.
    - Existing users whose `email` is still a `<clerk_id>@clerk.placeholder` value are backfilled on next sign-in (one-shot lookup; if the API call fails the user is left as-is).
    - The Clerk lookup is best-effort: if `LABSMITH_CLERK_SECRET_KEY` isn't configured or the request fails, the code falls back to JWT claims (email/name/picture) and finally to the placeholder. This means dev environments without a backend secret key still work; they just show the placeholder until configured.
    - Helper functions: `_fetch_clerk_user_profile`, `_profile_from_clerk_payload`, `_profile_from_jwt`.
  - **Webhook continues to be the canonical sync path** for created/updated/deleted users (`POST /api/v1/auth/webhook`). The Clerk Backend API call in `get_current_user` is the fallback for users who hit the API before the webhook fires (or in setups where webhooks aren't configured).
  - **Documented Clerk JWT expectations** (below). Default Clerk session JWTs only include `sub`, `iat`, `exp`, etc. — no profile claims. Two ways to surface real profile data: (a) configure a JWT template in Clerk dashboard, or (b) rely on the Backend API lookup we just added. Option (b) is the default in this repo.
  - **Documented the Next.js 16 `middleware → proxy` deprecation** (below). Kept `frontend/src/middleware.ts` as-is because `@clerk/nextjs` does not yet ship a `clerkProxy()` equivalent of `clerkMiddleware()` (the `proxy.d.ts` shipped by Clerk is for a different concept — proxying Clerk Frontend API requests, not the Next.js file-convention rename). The build warning is cosmetic; will migrate once Clerk publishes a proxy wrapper.
- Verified: `npm run backend:test` (20 tests), `npm --prefix frontend run lint`, `npm --prefix frontend run build`.

#### Clerk integration notes (for M3 and beyond)

**JWT claims expected.** By default Clerk session JWTs include only `sub` (the `clerk_user_id`), `sid`, `iat`, `exp`, `iss`, `nbf`. Profile fields (email, name, image_url) are NOT in the default token. Backend code must either:
1. Fetch the user from `https://api.clerk.com/v1/users/{id}` with the secret key (current implementation), or
2. Configure a JWT template in the Clerk dashboard that includes `email`, `name`, `image_url` claims, and rely on those.

**Webhook expected events.** `POST /api/v1/auth/webhook` handles `user.created`, `user.updated`, `user.deleted`. Configure the webhook in Clerk Dashboard → Webhooks, point it at `<backend>/api/v1/auth/webhook`, and copy the signing secret into `LABSMITH_CLERK_WEBHOOK_SECRET`. Without the secret, signature verification is skipped (dev only — must be configured for production).

**Required env vars** (`backend/.env`):
- `LABSMITH_CLERK_SECRET_KEY` — required for the user backfill lookup
- `LABSMITH_CLERK_PUBLISHABLE_KEY` — informational, mirrors the frontend value
- `LABSMITH_CLERK_JWKS_URL` — public JWKS endpoint, e.g. `https://<instance>.clerk.accounts.dev/.well-known/jwks.json`. The instance domain is base64-encoded inside the publishable key.
- `LABSMITH_CLERK_WEBHOOK_SECRET` — `whsec_...` from the webhook config; only required in production.

#### Known warnings (non-blocking)

- **Next.js**: `The "middleware" file convention is deprecated. Please use "proxy" instead.` Cosmetic. Will migrate `frontend/src/middleware.ts` → `proxy.ts` once `@clerk/nextjs` adds a `clerkProxy()` export. Rolling our own `proxy.ts` would mean re-implementing Clerk's middleware logic — not worth the risk before M3.
- **`react-hooks/set-state-in-effect`**: ESLint rule from React 19 flagging async data-fetch effects. We `// eslint-disable-next-line` those specific lines (sidebar tree fetch, workspace fetch, session detail fetch). The pattern is correct — the rule is a heuristic that doesn't recognize legitimate fetch-on-mount.

---

## Milestone 3: Chat-Based Design Sessions — IN PROGRESS

Both agents work to the contract at `docs/M3_CONTRACT.md`. Branches: `m3_akim` (backend), and a frontend branch on the teammate's machine.

### M3 backend — Day-1 mock-mode landing (this branch, `m3_akim`) — DONE

The backend is ready for the frontend to develop against. Mock mode is on by default; the frontend can stream a deterministic event sequence with no LLM and no CadQuery dependency.

#### What shipped
- **Routers** under `backend/app/routers/`:
  - `chat.py` — `POST /api/v1/sessions/{session_id}/chat` returns a `text/event-stream`. Calls `prepare_chat_turn` synchronously for preflight (auth, archived-session check, persisting the user message) so HTTP errors come back as proper 4xx instead of being raised mid-stream after headers ship.
  - `messages.py` — `GET /api/v1/sessions/{session_id}/messages` returns all messages oldest-first; used to hydrate the chat panel on load/refresh.
  - `artifacts.py` — `GET /api/v1/sessions/{session_id}/artifacts` returns artifacts newest-first. `download` and `preview` routes are reserved as `501 Not Implemented` — bodies land in M4 (storage/3D viewer) and M5 (real STL bytes).
- **Service**: `backend/app/services/chat.py` orchestrator, split into:
  - `prepare_chat_turn()` — synchronous preflight: session lookup + member role check + archived check + persist user message
  - `stream_chat_turn()` — async generator yielding `{event, data}` dicts in the order defined by the contract
  - `_orchestrate()` — the inner state machine. Adds the assistant `Message` to the session as a placeholder up-front (so any artifact rows can FK-reference it), streams `text_delta`s, runs the rule-based parser, emits `spec_parsed` + validation, runs (mock) generation, emits `generation_complete`, finalizes message metadata, then commits everything in a single transaction at `message_complete`.
- **Schemas**: `backend/app/schemas/chat.py`, `messages.py`, `artifacts.py`.
  - `MessageResponse` uses `validation_alias="metadata_"` so the ORM's `metadata_` attribute (renamed to dodge SQLAlchemy's reserved name) maps cleanly to `metadata` on the wire.
- **Mock mode** (`LABSMITH_CHAT_MOCK=true`, default `True`):
  - Canned assistant text streamed as 5 chunks with `asyncio.sleep(0.15)` between deltas
  - Rule-based parser produces a real `PartRequest` from the user prompt — same parser used by the legacy `/design` endpoint, so spec extraction is honest even in mock mode
  - Validation issues come from the existing `validate_part_request`
  - "Generation" is a 0.4s sleep + an `Artifact` row with `file_path=None` and `file_size_bytes=12345` (fake). M5 will write real STL bytes.
  - Versioning: each `generation_complete` increments `Artifact.version` per session.
- **Wiring**: new routers added to `backend/app/main.py`. `chat_mock` flag added to `app/config.py`.

#### Tests (`backend/tests/test_chat_api.py`)
Five new tests exercise the SSE pipeline end-to-end against the real Postgres database:
1. Full event sequence ordering (`text_delta` → `spec_parsed` → `generation_started` → `generation_complete` → `message_complete`) with persistence checks for both messages and the artifact.
2. Re-running the same prompt creates `version=2` artifact in the same session.
3. Unparseable prompts skip `spec_parsed` and `generation_*` and only emit `message_complete`.
4. Archived sessions reject the chat request with 409 (preflight, no SSE stream started).
5. Empty content returns 422.

Full backend suite: **25 tests passing** (20 existing + 5 new).

#### What the frontend agent can build against right now
- `POST /api/v1/sessions/{id}/chat` with body `{"content": "..."}` → SSE stream conforming exactly to the contract
- `GET /api/v1/sessions/{id}/messages` → hydration data
- `GET /api/v1/sessions/{id}/artifacts` → artifact list (real rows, fake byte counts)
- Auth + lab-membership rules unchanged — the existing Clerk Bearer token works on every endpoint

#### Open work for M3 backend (still to come on this branch or later)
- Replace `_build_assistant_text_chunks` with a real LLM call (OpenAI or similar). Public surface stays the same — it's still an iterator yielding `text_delta` payloads.
- Replace `_run_generation` with real CadQuery export when M5 lands. Until then, artifacts have `file_path=None`.
- Wire up rate limiting on `/chat`. Stubbed for now.
- Heartbeat (`:keepalive`) in long pauses — contract says SHOULD; not yet emitted because mock mode is fast enough that no proxy timeout is plausible. Add when LLM streams introduce real latency.

### Subsequent Milestones
- **M4**: 3D preview + file downloads (React Three Fiber STL viewer; fills in `download` + `preview` route bodies)
- **M5**: Real CadQuery integration (replace mock generation)
- **M6**: Polish + deployment (Docker, error handling, rate limiting)
