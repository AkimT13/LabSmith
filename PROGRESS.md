# LabSmith — Implementation Progress

## Milestone 1: Project Restructure + Database + Auth — COMPLETE

### What was done

#### Backend Restructure
- Created `backend/app/` as the new application layer alongside the existing `backend/src/labsmith/` CAD pipeline
- **Entry point**: `backend/app/main.py` → `app.main:app`
- **Root compatibility route**: `/health` remains available. The old scaffold routes `/templates`, `/parse`, and `/design` are no longer exposed by the product API.
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
- `@clerk/nextjs` for auth — Next proxy protects all routes except `/`, `/sign-in`, `/sign-up`
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
- `test_app.py` verifies `/health`, v1 OpenAPI metadata, removal of old scaffold routes, and auth returns 401 without token
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
      chat.py            # authenticated session chat endpoint
    schemas/
      auth.py            # UserResponse pydantic model
  src/labsmith/          # Original CAD pipeline (unchanged)
    parser/              # RuleBasedParser
    templates/           # Tube rack and gel comb
    validation/          # Part request validation rules
    export/              # Export plan (stubs — no real CAD yet)
    models.py            # Pydantic domain models (PartRequest, etc.)
  alembic/
    env.py               # Async Alembic env
    versions/
      0975421fbff3_initial_schema.py
  tests/
    test_api.py          # Legacy API tests
    test_app.py          # App tests (/health, v1 metadata, auth 401)
    test_parser.py       # Parser unit tests
    test_templates.py    # Template registry tests
    test_validation.py   # Validation rule tests
  .env                   # LABSMITH_* env vars (not committed)
  .env.example           # Template for .env
  alembic.ini

frontend/
  src/
    proxy.ts                  # Clerk route protection
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
  - **Next.js 16 proxy convention**: route protection now lives in `frontend/src/proxy.ts`, using the same Clerk wrapper logic that previously lived in `middleware.ts`.
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

- **`react-hooks/set-state-in-effect`**: ESLint rule from React 19 flagging async data-fetch effects. We `// eslint-disable-next-line` those specific lines (sidebar tree fetch, workspace fetch, session detail fetch). The pattern is correct — the rule is a heuristic that doesn't recognize legitimate fetch-on-mount.

---

## Milestone 3: Chat-Based Design Sessions — IN PROGRESS

Both agents work to the contract at `docs/M3_CONTRACT.md`. Branches `m3_akim` (backend) and `m3-frontend` (frontend) have both been merged into `main`.

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
  - Rule-based parser produces a real `PartRequest` from the user prompt, so spec extraction is honest even in mock mode
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

### M3 frontend — Chat session UI landing (branch `m3-frontend`) — DONE

The frontend is wired to the M3 contract surface and can run against Akim's mock-mode backend stream.

#### What shipped
- **API contract helpers** in `frontend/src/lib/api.ts`:
  - `PartRequest`, `ValidationIssue`, `Message`, and `Artifact` TypeScript types mirror `docs/M3_CONTRACT.md`
  - `fetchMessages`, `fetchArtifacts`, and `postChat`
  - `postChat` returns the raw stream response so the hook can parse SSE events
- **SSE hook** in `frontend/src/lib/use-chat.ts`:
  - Uses authenticated `fetch` with the Clerk Bearer token instead of `EventSource`
  - Parses `text_delta`, `spec_parsed`, `generation_started`, `generation_complete`, `message_complete`, and `error`
  - Maintains live assistant message text, parsed spec state, validation issues, generation state, and inline errors
  - Refreshes persisted messages after each completed stream
- **Session components** under `frontend/src/components/sessions/`:
  - `chat-panel.tsx` — message list, input, refresh action, streaming state, and archived-session read-only behavior
  - `message-bubble.tsx` — user/assistant message rendering
  - `spec-card.tsx` — parsed spec display plus generation status
  - `validation-badge.tsx` — validation summary badge
  - `artifact-list.tsx` — artifact list with manual refresh and file-size display
- **Session detail route** at `/dashboard/sessions/[sessionId]`:
  - Replaced the M2 placeholder card with the M3 chat panel
  - Added artifact list refresh on `generation_complete`
  - Added a reserved M4 viewer panel; preview/download bodies remain out of M3 scope

#### Verification
- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`

#### Open work for M3 backend (still to come on this branch or later)
- Replace `_build_assistant_text_chunks` with a real LLM call (OpenAI or similar). Public surface stays the same — it's still an iterator yielding `text_delta` payloads.
- Replace `_run_generation` with real CadQuery export when M5 lands. Until then, artifacts have `file_path=None`.
- Wire up rate limiting on `/chat`. Stubbed for now.
- Heartbeat (`:keepalive`) in long pauses — contract says SHOULD; not yet emitted because mock mode is fast enough that no proxy timeout is plausible. Add when LLM streams introduce real latency.

---

## Milestone 4: 3D Preview + File Downloads — IN PROGRESS

Both agents work to the contract at `docs/M4_CONTRACT.md`. Branches: `m4_akim` (backend, this branch), and a frontend branch on the teammate's machine.

### M4 backend — Day-1 storage + download/preview routes (this branch, `m4_akim`) — DONE

The backend now persists artifact bytes to disk and serves them through real download/preview endpoints. Mock mode writes a placeholder STL so the frontend's 3D viewer has bytes to render before M5's real CadQuery output lands.

#### What shipped
- **Storage abstraction** in `backend/app/services/storage.py`:
  - `StorageBackend` protocol (`save`, `read`, `exists`, `delete`) so S3/R2/Spaces is a one-class swap-in later. `Artifact.file_path` stores an opaque storage key, not an absolute path.
  - `LocalFilesystemStorage` writes under `LABSMITH_STORAGE_DIR` (default `./backend/storage`, gitignored). Defends against absolute keys and parent-traversal.
  - `get_storage()` factory returns a singleton; `reset_storage_for_testing()` lets tests rebuild it after settings overrides.
  - `artifact_storage_key()` enforces the canonical key shape: `sessions/<session_id>/artifacts/<artifact_id>-v<version>.<ext>`. Version is folded into the filename so re-generation never overwrites prior bytes — keeps `If-None-Match` cache valid.
- **Mock-mode placeholder STL** (`backend/app/services/placeholder_stl.py`): a deterministic 10mm unit cube, 684 bytes binary STL. `_run_generation` now writes it via the storage backend in mock mode and populates real `file_path` + `file_size_bytes` on the artifact row. M5 will replace the byte source with real CadQuery output without changing the persistence path.
- **`GET /api/v1/artifacts/{id}/download`**: serves the stored bytes with `Content-Disposition: attachment; filename="<slug>-v<version>.<ext>"` (RFC 5987 fallback for non-ASCII titles), `Cache-Control: private, no-cache`, correct `Content-Length`. 404 when `file_path` is null or bytes are missing on disk.
- **`GET /api/v1/artifacts/{id}/preview`**: serves STL bytes inline (no `Content-Disposition`), with `ETag: "<artifact_id>:v<version>"` and `Cache-Control: private, max-age=300`. Honors `If-None-Match` for `304 Not Modified` so the browser doesn't re-download identical bytes after a `generation_complete` event. Non-STL artifacts return `415`.
- **`ArtifactResponse` schema** now exposes computed `download_url` and `preview_url` fields. Both are null when `file_path` is null; `preview_url` is also null for non-STL artifacts so the viewer cleanly degrades to its empty state. The frontend never builds these URLs by hand.
- Auth + lab membership rules unchanged: same `_resolve_artifact_and_session` helper checks the caller is at least a viewer of the artifact's lab.
- CORS now exposes `ETag`, `Content-Disposition`, and `Content-Length` so browser-side preview/download code can read cache and filename metadata.
- New config in `app/config.py`: `storage_backend` (default `"local"`) and `storage_dir`.
- `.gitignore` now ignores `backend/storage/` so dev artifacts don't get committed.

#### Tests
- `backend/tests/test_storage.py` — 10 tests covering save/read/exists/delete roundtrip, missing-key errors, parent-dir creation, absolute-path + parent-traversal rejection, key-shape contract, singleton behavior.
- `backend/tests/test_artifact_endpoints.py` — 7 tests covering download with correct headers + bytes, preview with ETag, `304 Not Modified` on matching `If-None-Match`, response shape includes `download_url` + `preview_url`, 415 for non-STL preview, 404 for unknown artifacts, 403/404 for non-members of the lab.
- `backend/tests/test_chat_api.py` updated: assertions now confirm mock generation produces non-null `file_path`, real `file_size_bytes` matching the placeholder STL, and that the response carries `download_url` + `preview_url`.
- `backend/tests/conftest.py` autouse fixture redirects `LABSMITH_STORAGE_DIR` to a per-test tmp directory, so the suite never accumulates artifact bytes in the dev tree.

Full backend suite: **42 tests passing**.

#### What the frontend agent can build against right now
- `GET /api/v1/sessions/{id}/artifacts` returns artifacts whose responses include `download_url` and `preview_url` fields.
- `GET /api/v1/artifacts/{id}/preview` returns real STL bytes (mock placeholder cube for now), `Content-Type: model/stl`, ETag-cached.
- `GET /api/v1/artifacts/{id}/download` returns the same bytes as a `Content-Disposition: attachment` payload. Frontend should fetch with the Clerk Bearer token, then trigger the download via `Blob` → `URL.createObjectURL` → synthetic `<a download>` click (since plain `<a href>` can't carry the auth header).
- After a `generation_complete` SSE event, the artifact list refresh already returns the new artifact with a populated `preview_url`. The `<StlViewer>` reload-on-event pattern from the contract works against today's backend.
- `frontend/src/lib/api.ts` includes `fetchArtifactResponse()` for authenticated artifact byte requests and API-relative URL normalization via `buildApiUrl()`.
- `frontend/src/components/sessions/artifact-list.tsx` now uses authenticated fetch for downloads and reads filenames from `Content-Disposition`.

### M4 frontend — STL viewer + session-page integration — DONE

The session page now renders authenticated STL previews from the M4 artifact endpoints. This keeps the frontend aligned with the contract's auth requirement: preview/download bytes are fetched with the Clerk Bearer token, not loaded through plain URLs.

#### What shipped
- Added Three.js viewer dependencies to the frontend workspace: `three`, `@types/three`, and `@react-three/fiber`.
- Added `frontend/src/components/sessions/viewer-panel.tsx`:
  - selects an STL artifact with `preview_url`
  - fetches preview bytes with `fetchArtifactResponse()`
  - sends `If-None-Match` when reloading the same artifact
  - reuses cached geometry on `304 Not Modified`
  - parses bytes with `STLLoader.parse(arrayBuffer)`
  - handles empty, loading, error, and retry states
- Added `frontend/src/components/sessions/stl-viewer.tsx`:
  - renders the STL in a React Three Fiber `<Canvas>`
  - recenters geometry, computes normals, adds lighting, grid, and orbit controls
  - avoids `@react-three/drei` so the frontend does not inherit its Node 22 engine warning under the current Node 20 dev environment
- Updated `/dashboard/sessions/[sessionId]` to replace the M2/M3 placeholder viewer card with the live `ViewerPanel`.
- Changed the default frontend dev/build scripts to webpack (`next dev --webpack`, `next build --webpack`) after local dev showed a memory blow-up during Next.js 16.2.4 Turbopack route compilation. `turbopack.root` is scoped to the frontend app, and `npm --prefix frontend run dev:turbo` remains available for reproducing/debugging Turbopack specifically.
- Updated the dashboard `UserButton` usage for the installed Clerk version by removing the stale `afterSignOutUrl` prop.

#### Verification
- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`

#### Manual UI test still needed
- Start backend + frontend, open a session, generate a mock part, and confirm the artifact list refreshes, the STL preview renders, orbit controls work, retry reloads cleanly, and download still saves the authenticated artifact.

#### Open work for M4 backend (likely after frontend integrates)
- Streaming response (`iter_bytes`) for large artifacts. Today the route reads the whole file into memory — fine for the placeholder cube (684 B) and small CadQuery output, but should switch when files exceed ~10MB.
- Object-store backends (S3, R2). Protocol is shaped for them; only `LocalFilesystemStorage` ships.
- The `download` route currently returns the same bytes regardless of `artifact_type`. Once M5 lands real STEP export, double-check the MIME type (`model/step` vs `application/step`) actually round-trips through browsers cleanly.

### Subsequent Milestones

> **Renumbering note:** the original plan had M5 = real CadQuery. After M4 we decided to insert a "Session Types + Agent Abstraction" milestone first, so CadQuery moved to M6, deployment to M7, and the onboarding agent (a teammate-driven idea) got its own slot at M8.

## Milestone 5: Session Types + Agent Abstraction — COMPLETE

Branch: `m5_akim`. Backend extraction + onboarding stub + frontend type picker shipped.

### What shipped (this branch)

#### Backend
- **`SessionType` enum** added to `backend/app/models/design_session.py` with values `PART_DESIGN` and `ONBOARDING`. Stored on the existing `design_sessions` table — no rename of the model class (kept `DesignSession` to minimize blast radius; the type column does the polymorphism).
- **Alembic migration** `b6d58704dee5_add_session_type_to_design_sessions.py` adds the column with `server_default='PART_DESIGN'` so existing rows backfill cleanly. Explicitly creates the Postgres enum type via `Enum.create(...)` since asyncpg doesn't auto-create enum types as a side effect of `add_column`.
- **`SessionAgent` protocol** in `app/services/agents/base.py` — single `async run_turn(db, session, user, user_content) -> AsyncIterator[AgentEvent]` method. Agents own their event catalog; the dispatcher is type-agnostic.
- **`PartDesignAgent`** in `app/services/agents/part_design.py` — the M3/M4 orchestrator lifted out of `chat.py` verbatim. Same event catalog (`text_delta` → `spec_parsed` → `generation_started` → `generation_complete` → `message_complete`), same persistence path, same mock-mode placeholder STL.
- **`OnboardingAgent`** in `app/services/agents/onboarding.py` — stub that streams a placeholder reply ("real onboarding lands in M9") via `text_delta` + `message_complete` only. Intentionally minimal so the frontend's existing `useChat` hook needs no new event handlers. M9 will replace the body with real RAG / checklist behavior; the agent class signature stays.
- **Registry** in `app/services/agents/registry.py` — hardcoded `SessionType → agent instance` mapping. `get_agent_for_session(session)` is the only entry point; raises loudly if a registered `SessionType` value lacks an agent.
- **`chat.py` slimmed** to a dispatcher: `prepare_chat_turn()` for preflight (unchanged), `stream_chat_turn()` looks up the agent and forwards its events, wrapping in a try/except that converts unhandled errors to a single `error` event.
- **Schemas updated**: `DesignSessionCreate` accepts `session_type` (defaults to `PART_DESIGN`). `DesignSessionUpdate` does NOT include `session_type` — it's set-once at creation and immutable thereafter, so PATCH attempts to change it are silently dropped by Pydantic. `DesignSessionResponse` now exposes `session_type`.
- **Service layer**: `create_session` writes the supplied (or default) `session_type` to the new column.

#### Frontend
- **`SessionType` type** added to `frontend/src/lib/api.ts` (`"part_design" | "onboarding"`). `DesignSession` interface gains the field. `createSession` now accepts an optional `session_type` argument.
- **Session form dialog** (`session-form-dialog.tsx`) — when in create mode, shows a session-type picker with friendly descriptions ("Part design — describe a 3D-printable part…", "Onboarding — lab orientation guidance"). Hidden in edit mode because session_type is immutable. The "Part type" field auto-hides when the user picks `onboarding` (it's only meaningful for `part_design`).
- **Workspace page** (`/dashboard/labs`) passes `showSessionType={true}` on create, `false` on edit. The PATCH path explicitly drops `session_type` so the frontend mirrors the backend's immutability rule.
- **Session detail page** (`/dashboard/sessions/[sessionId]`) routes on `session.session_type`:
  - `part_design` → existing M3/M4 layout (chat panel + artifact list + 3D viewer)
  - `onboarding` → chat-only full-width layout with a "preview surface" notice card explaining M8 will fill it in
- Header copy is type-aware ("Part design session" vs "Onboarding session"), and the "No part type set" subtitle is hidden for non-design types.

#### Tests
- New `backend/tests/test_agents.py` (7 tests):
  - Registry returns the right agent for each `SessionType`
  - `session_type` defaults to `part_design` on creation
  - Creating with `session_type=onboarding` persists and round-trips through `GET`
  - PATCH cannot change `session_type` (extra field is silently dropped, type stays put)
  - `part_design` agent emits the full M3 event catalog (regression test for the extraction)
  - `onboarding` agent emits only `text_delta` + `message_complete`, no spec/generation events, and produces no artifacts
- All 5 existing chat-API tests still pass unchanged — the extraction was behavior-preserving.
- Full backend suite: **49 tests passing** (was 42 before M5; +7 new agent tests).

### Build / lint status
- `npm run backend:test` passes after running `npm run backend:migrate`.
- `npm --prefix frontend run lint` passes.
- `npm --prefix frontend run build` passes with the webpack script.

### Open work for M5 follow-up
- Onboarding agent's body (RAG, checklists) is M8 — left as a stub on purpose.

### Decisions made (the open questions from the planning entry)
1. **Renamed `DesignSession`?** No — kept the class name. The `session_type` column does the polymorphism; renaming would have churned ~20 files for cosmetic value.
2. **`session_type` immutable?** Yes — enforced by leaving it out of `DesignSessionUpdate`.
3. **`current_spec` → `state`?** No — kept `current_spec`. It's still JSONB; semantics generalize without a rename.
4. **Registry hardcoded?** Yes.
5. **Backfill existing rows?** Yes — `server_default='PART_DESIGN'` in the migration handles it.

#### M6 — Real CadQuery Integration (was M5) — COMPLETE

Scoped specifically to the `part_design` agent's generator. Replaced the placeholder STL with real geometry from CadQuery. Everything else (persistence, storage, routes, viewer) is unchanged from M4 — M6 is a byte-source swap behind the same artifact contract.

- `cadquery>=2.4` is now a real backend dependency instead of an optional extra.
- New `backend/app/services/cad_generation.py` returns generated artifact bytes for supported part-design specs.
- Implemented real STL builders for `tube_rack` and `gel_comb`.
- CadQuery export runs through `asyncio.to_thread` so native CAD work does not block the event loop.
- `settings.chat_mock=true` now controls scripted text/pacing only; valid supported specs still generate real CAD.
- STEP remains deferred; M6 produces STL only and does not create fake STEP artifacts.
- Golden-spec tests verify generated STL validity, dimensions, and that bytes do not match the legacy placeholder cube.
- Full backend suite: **51 tests passing**.

## Milestone 7: Smart Parsing & Iterative Refinement — COMPLETE

> **Renumbering note:** original plan had M7 = deployment. After M6 we noticed the LLM work was wedged into M7 ambiguously — the assistant-text streaming is a small swap, but the *structured-output parameter extraction* (replacing the regex parser, supporting "make the wells deeper" follow-ups) is the bigger piece that actually delivers natural-language → CAD. They earned their own milestone. Deployment moved to M8, onboarding agent to M9.

Branch: `m7_akim`. Backend pluggable LLM + spec extraction shipped behind feature flags; mock paths remain the default so nothing requires an API key.

### What shipped (this branch)

#### Backend
- **`app/services/llm.py`** — assistant-text streaming abstraction.
  - `LLMProvider` Protocol with one method, `stream_response(user_content) -> AsyncIterator[str]`.
  - `MockLLMProvider` — canned response with cosmetic pacing (default).
  - `OpenAIProvider` — lazy-imports the `openai` SDK, streams Chat Completions chunks with the configured system prompt. Raises a clear `ValueError` if no API key is configured.
  - `get_llm_provider()` factory — reads `LABSMITH_CHAT_LLM_PROVIDER` (default `mock`).
- **`app/services/spec_extraction.py`** — structured `PartRequest` extraction abstraction.
  - `RuleBasedExtractor` — wraps the existing regex parser. Now also consults `current_spec` and falls through to `parser.parse_update()` for follow-up turns (so iterative phrasing works even without an LLM, within the parser's regex limits).
  - `OpenAIExtractor` — uses OpenAI's `response_format={"type": "json_schema", "strict": True}` against a hand-written PartRequest schema. Gets `current_spec` and the last 16 messages of conversation history as system context, so phrases like "make the wells 5mm deeper" patch the existing spec instead of failing the part-type detection. **Falls back to `RuleBasedExtractor` on ANY failure** (network error, malformed JSON, validation error) — a misconfigured key never crashes a chat turn.
  - `get_spec_extractor()` factory — reads `LABSMITH_SPEC_EXTRACTOR` (default `rule_based`).
  - `messages_to_chat_history()` helper — converts ORM `Message` rows to the OpenAI chat-history shape, dropping system/empty rows.
- **`agents/part_design.py` rewired**:
  - `_build_assistant_text_chunks` (the canned-text helper) deleted; agent now iterates `provider.stream_response(...)`.
  - `_parse_prompt` (the inline regex wrapper) replaced by `extractor.extract(user_content, current_spec=session.current_spec, message_history=...)`.
  - New helper `_load_prior_chat_history()` snapshots prior message rows BEFORE the assistant placeholder is added, so the extractor sees a clean record. Trims the most-recent user row because it's already passed separately as `user_content`.
  - Assistant message metadata now includes `extraction_source` so we can tell apart "OpenAI extracted it" from "OpenAI failed and rule-based covered it" when debugging.
- **Config additions** (`app/config.py`):
  - `chat_llm_provider` (default `mock`)
  - `spec_extractor` (default `rule_based`)
  - `openai_api_key` (empty by default)
  - `openai_chat_model` / `openai_extraction_model` (both `gpt-4o-mini`)
  - `openai_chat_system_prompt` (system prompt for the assistant reply)
- **`pyproject.toml`** — `openai>=1.30` moved from optional `[llm]` extra to required dependencies. The package is now imported lazily inside the OpenAI-flavored classes, so simply having it installed costs nothing at import time.
- **`backend/.env.example`** — documents all four new env vars and explains when keys are needed.

#### Tests (all green; no real OpenAI calls)
- `backend/tests/test_llm_provider.py` — 4 tests: factory selection, fallback on unknown values, mock chunk shape, OpenAI key validation.
- `backend/tests/test_spec_extraction.py` — 11 tests: factory, rule-based fresh-parse, rule-based iteration via current_spec, OpenAI valid-response parsing, OpenAI null-part-type passthrough, OpenAI fallback on network errors, OpenAI fallback on malformed JSON, history filtering. The OpenAI tests use a stub `_StubOpenAI` client to avoid network calls.
- All existing M3/M4/M5/M6 tests still pass — extraction is behavior-preserving for the default rule-based path.
- Follow-up parser polish: labeled bare dimensions default to millimeters, while explicit `cm`, `m`, `in`, `ft`, `um`, and `nm` values convert into internal millimeters.
- Full backend suite: **75 tests passing** (was 55 before M7; +20 new).

### How to enable real OpenAI

Two independent flags so you can mix-and-match — e.g., real LLM text with rule-based extraction, or vice versa:

```bash
# in backend/.env
LABSMITH_OPENAI_API_KEY=sk-proj-...
LABSMITH_CHAT_LLM_PROVIDER=openai      # real assistant text streaming
LABSMITH_SPEC_EXTRACTOR=openai         # smart parameter extraction + iteration
LABSMITH_OPENAI_CHAT_MODEL=gpt-4o-mini       # optional override
LABSMITH_OPENAI_EXTRACTION_MODEL=gpt-4o-mini # optional override
```

Restart the backend. No code changes needed; the agent picks up the new provider on the next chat turn.

### What this unlocks (visible to users)
- Free-form prompts that the regex parser never understood: "I need a rack that fits 50mL Falcon tubes."
- Iterative refinement: the user can say "actually make it 5x8 instead" or "spacing should be 18 mm" and the existing spec is patched, not re-parsed.
- Better acknowledgement text: the canned "Got it — looking at..." is replaced by a real conversational reply.

### What's NOT in M7 (deferred to M8)
- Deployment (Docker, managed Postgres, S3/R2 storage, rate limiting, heartbeat events).
- Real LLM tool-calling beyond simple structured output (e.g., "search the lab for similar parts").

### Open work for M7 follow-up
- Frontend has no surface for surfacing the `extraction_source` metadata. If we want users to know "this was generated via natural language" vs "fell back to rule-based," that's a small UI addition.
- The OpenAI extractor doesn't yet stream — it makes a single completion call. Streaming structured output exists in the API but isn't worth the complexity for this use case (the call is fast enough; the streamed text is the user-visible part).

### Part type expansion (shipped alongside M7)

The supported part-type catalog now includes pipette tip racks and petri dish stands. With the M7 LLM extractor, each type is accessible through natural language via the same structured spec contract.

- **`pipette_tip_rack`** — two-plate rack with tip slots in the top plate, drain holes in the bottom, and corner posts. Defaults to 96 tips / 6.5 mm slots / 50 mm tall.
- **`petri_dish_stand`** — vertical four-pillar stand with side slots that hold round dishes. `well_count` is the number of dish slots; `diameter_mm` is the dish diameter (90 or 100 typical).

Wired through every layer:
- `PartType` enum includes the supported generated values.
- Rule-based parser detects pipette tip racks with priority ordering (`pipette tip` checked before `tube rack` so "pipette tip rack" doesn't get misclassified).
- `_apply_part_defaults` ships sensible defaults so under-specified prompts still produce something.
- Validation rules added per-type with friendly clarification messages.
- `cad_generation.py` includes builders for tube racks, gel combs, pipette tip racks, and petri dish stands.
- OpenAI extraction system prompt updated with the supported types' field-mapping guidance.

Tests cover golden-spec CAD dimensions and natural-language detection, especially that "pipette tip rack" doesn't get caught by the generic tube-rack rule.

#### M8 — Polish + Deployment (was M7)

Status: in progress; local Docker/chat/security/UX hardening is done, deploy-provider items remain.

- [x] Dockerfiles (backend + frontend)
- [x] docker-compose.yml (backend, frontend, postgres)
- [x] Build Docker images and smoke-test backend + Postgres compose health
- [ ] Smoke-test frontend compose with real Clerk env
- [ ] Object-store storage backend (S3 / R2 / Spaces) plugged in behind `StorageBackend` if multi-instance deploy is on the table; local FS stays as the dev path
- [ ] Managed Postgres migration (Neon / Supabase / RDS)
- [x] Rate limiting on `/chat`
- [x] Heartbeat (`:keepalive`) SSE events for long LLM pauses
- [x] Error handling pass, loading skeletons, toast notifications on primary session surface
- [x] Artifact storage path traversal hardening (invalid keys reject cleanly; downloads return 404 instead of 500)
- [x] Security audit pass (auth required, IDOR regression coverage, path traversal hardening)
- [ ] Dependency audit follow-up: `npm audit --omit=dev` reports 3 moderate PostCSS issues through Next/Clerk with no fix available in the current tree
- [x] OpenAPI docs polish

#### M8.1 — Part Design Trust + Iteration Polish — COMPLETE

This is a product polish layer on top of the existing part-design/STL pipeline, not a new milestone family.

- Added selectable artifact gallery behavior so users can preview/download prior generated STL versions instead of only seeing the newest artifact.
- Added bounding-box fit constraints to `PartRequest`: `max_width_mm`, `max_depth_mm`, and `max_height_mm`.
- Parser supports prompts such as "fit within 100 x 80 x 60 mm" and "fit in a 10 cm by 8 cm drawer", with unit conversion into millimeters.
- Validation blocks generation when the estimated part dimensions exceed explicit fit constraints.
- Added a lightweight printability report persisted on artifact validation metadata:
  - estimated bounding-box size
  - common desktop-printer bed fit
  - wall-thickness check
  - support-risk advisory
  - stability advisory
  - rough PLA material estimate
- Surfaced printability information in the parsed spec and artifact list.
- Kept printability labeled as heuristic/advisory; this is not slicer-backed print-time or material simulation.

#### M9 — Onboarding Agent (was M8)

Real implementation of the lab onboarding agent stubbed in M5. Targets the pain point of new lab members not knowing where things are, what protocols apply, who owns what.

Status: in progress; deterministic v0 + lab document metadata + retrieval-augmented replies (lexical + OpenAI embeddings) are implemented. Multipart file upload, persistent embedding cache, and onboarding-specific frontend panels remain.

- [x] `docs/M9_CONTRACT.md` defines onboarding/file-maker ownership boundaries
- [x] Deterministic onboarding v0 agent
- [x] Onboarding event catalog coverage (`topic_suggested`, `checklist_step`, `text_delta`, `message_complete`)
- [x] Frontend onboarding copy updated from placeholder wording
- [x] Lab document model, migration, JSON text upload/list/download endpoints
- [x] Onboarding replies can mention available lab document records
- [x] **Retrieval-augmented onboarding replies** — agent now reads document text, chunks it, scores chunks against the user query, and incorporates the top snippets into the reply.
- [x] **Citations + `doc_referenced` events** — every cited document produces a `doc_referenced` SSE event with title, document_id, source, and download URL. Assistant message metadata pins `cited_documents` (id, title, score) and `doc_backed: true`.
- [x] **Membership-scoped retrieval** — documents are loaded by `lab_id` derived from the session's project, so a session in Lab A can never retrieve from Lab B even when the same user owns both. Pinned by a regression test.
- [x] **Pluggable retriever backends** — `LexicalRetriever` (TF-IDF-style, default) and `OpenAIEmbeddingRetriever` (semantic match, falls back to lexical on any failure). Selected via `LABSMITH_ONBOARDING_RETRIEVER`.
- [x] **Sample lab documents** — six realistic markdown SOPs/policies/rosters at `docs/sample_lab_documents/` plus a README with `curl + jq` upload script and example queries that exercise both lexical and semantic retrieval paths.
- [x] **Doc upload UI** — Lab Settings dialog now has a Documents section (member+ only) with a paste-text upload form (title + optional source filename + content-type select + textarea), document list with size/date, and an authenticated download button. Lives in `frontend/src/components/dashboard/lab-documents-section.tsx`.
- [x] **Onboarding-specific frontend panel** — `useChat` now captures `topic_suggested` / `checklist_step` / `doc_referenced` events. New `OnboardingTurnPanel` renders the topic, suggested questions, checklist, and clickable cited-document links inside the chat. `ChatPanel` is session-type-aware (different title, empty state, and input placeholder for onboarding vs design).
- [ ] Multipart doc upload (current path is JSON text only)
- [ ] Persistent embedding cache (today: embed per-turn; cheap at current doc sizes but wasted work if collections grow)

##### M9 retrieval — what shipped on `m9_akim`

**New module `backend/app/services/onboarding_retrieval.py`:**
- `chunk_document_text()` — paragraph-aware chunking with sentence-level fallback for long blocks. Targets `LABSMITH_ONBOARDING_CHUNK_MAX_CHARS` (default 600).
- `LexicalRetriever` — TF-IDF-ish scoring over the per-turn chunk pool. Bag-of-words tokenization with stopword + short-token filtering. Drops zero-score chunks rather than padding to k.
- `OpenAIEmbeddingRetriever` — embeds the query + all chunks in a single embeddings API call, scores by cosine. Falls back to lexical on any failure (network, malformed response, length mismatch).
- `Retriever` Protocol so a third backend (Cohere, local sentence-transformers, etc.) is one class away. `get_retriever()` factory reads `LABSMITH_ONBOARDING_RETRIEVER`.

**`agents/onboarding.py` rewired:**
- Loads documents *with text* (not just titles) via the existing storage backend. Best-effort UTF-8 decode — binaries/missing files are silently skipped for retrieval but still listed by title in the fallback note.
- Three reply branches kept stable:
  1. No documents at all → "I do not have uploaded lab documents connected yet" (existing wording, preserves the M9 v0 test).
  2. Documents exist but no chunk scored above zero → existing "available documents but semantic search not connected yet" wording (so prior tests pin the no-match branch).
  3. **NEW**: Documents exist AND retrieval found relevant snippets → "Based on your lab documents, here's what's most relevant" with snippets and a "Sources cited above" list.
- Emits `doc_referenced` events only when at least one chunk scored above zero (per contract §4 — title-only listing isn't enough).
- Stamps assistant message metadata with `doc_backed: true|false`, `retriever: "lexical"|"openai"|null`, and `cited_documents: [{document_id, title, score}]`.

**Config additions:**
- `LABSMITH_ONBOARDING_RETRIEVER` (`lexical` | `openai`), `LABSMITH_OPENAI_EMBEDDING_MODEL` (default `text-embedding-3-small`), `LABSMITH_ONBOARDING_CHUNK_MAX_CHARS`, `LABSMITH_ONBOARDING_TOP_K_CHUNKS`.
- All four documented in `backend/.env.example`.

**Tests added (16 new):**
- `backend/tests/test_onboarding_retrieval.py` — 14 unit tests covering factory selection, paragraph chunking, long-paragraph splitting, empty inputs, lexical relevance ordering, lexical top-k cap, OpenAI cosine scoring (with stubbed client), OpenAI fallback on network failure, OpenAI empty-chunks short-circuit, OpenAI empty-key rejection.
- `backend/tests/test_agents.py` — 3 new agent integration tests:
  - `test_onboarding_retrieves_same_lab_document_with_citation` — uploads a doc, queries against its content, asserts snippet in reply, `doc_referenced` event emitted with the doc's ID, metadata `doc_backed: true` + `cited_documents` populated, no design events / artifacts.
  - `test_onboarding_does_not_retrieve_other_lab_documents` — uploads doc to Lab B (same user owns both), queries from Lab A session, asserts NO `doc_referenced` events, NO citation in metadata, falls back to no-docs branch.
  - `test_onboarding_falls_back_to_titles_when_no_chunks_score_above_zero` — uploads a doc with disjoint vocabulary, queries against it, asserts the existing title-listing branch fires and no `doc_referenced` events emit.

**Verification:**
- Full backend suite: **126 passing** (was 110 before M9 retrieval; +16 new).
- `python3 -m ruff check backend/app/services/agents/onboarding.py backend/app/services/onboarding_retrieval.py backend/tests/test_agents.py backend/tests/test_onboarding_retrieval.py` — all green.
- No frontend changes in this slice (per the contract — onboarding-specific panels are deferred). The chat panel renders the new events through the existing `useChat` hook without modification.

##### Onboarding frontend — what shipped

Frontend pass to make M9 demo-ready, on top of the backend retrieval work above:

- **Lab Documents section** in the existing Lab Settings dialog (`frontend/src/components/dashboard/lab-documents-section.tsx`). Lists uploaded docs with size/upload-date; member+ users get a paste-text upload form (title + optional source filename + content-type select + textarea + submit). Each doc has an authenticated download button that fetches bytes through `downloadLabDocument()` (blob URL → synthesized click, since plain `<a href>` can't carry the Clerk Bearer token).
- **`useChat` extended** (`frontend/src/lib/use-chat.ts`) to capture the M9 onboarding events: `topic_suggested`, `checklist_step`, `doc_referenced`. New per-turn state `onboardingTopic`, `onboardingChecklist`, `onboardingCitations` resets at the start of each `sendMessage` call and at every new `topic_suggested` event.
- **`OnboardingTurnPanel`** (`frontend/src/components/sessions/onboarding-turn-panel.tsx`) renders the topic with rationale + suggested questions, the checklist as bordered cards, and citations as clickable links that route through `buildApiUrl()` + the user's auth token.
- **`ChatPanel` made session-type-aware**: title (`"Onboarding chat"` vs `"Design chat"`), empty state, input placeholder all switch on `sessionType`. The `SpecCard` only shows for design sessions; the `OnboardingTurnPanel` only shows for onboarding sessions.
- **Session detail page placeholder card** (`/dashboard/sessions/[sessionId]/page.tsx`) updated to point users at "Lab settings → Documents" instead of the stale "until lab document retrieval is connected" copy.
- New API surface in `lib/api.ts`: `LabDocument` type, `fetchLabDocuments`, `createLabDocument`, `downloadLabDocument`.
- Verified: `npm --prefix frontend run lint` clean, `npm --prefix frontend run build` green, `python3 -m pytest backend/tests` 126/126.

##### Open work for M9 follow-up

- Persistent embeddings store (`lab_document_chunks` table or JSONB column on `lab_documents`) so the OpenAI path doesn't re-embed on every turn. Cheap today; matters once collections grow past a handful of docs per lab.
- Multipart file upload — current `LabDocumentCreate` schema requires the body in a `content: str` JSON field. Fine for SOPs and protocols pasted as text; binaries can't ride this path.
- Document delete endpoint + UI — backend currently has no `DELETE /documents/{id}`; UI omits the action.
- Inline citation markers in the reply text (e.g. `[1]` linking to the cited doc) instead of a "Sources cited above" footer.

### Akim AM Handoff

Primary focus should be **M9 semantic onboarding over lab-uploaded docs**. Part-design trust polish is complete enough for now; do not start STEP export, slicer-backed estimates, or new CAD templates unless the M9 path is blocked.

Recommended next slice:

1. Read `docs/M9_CONTRACT.md` and the existing document endpoints before changing schemas.
2. Add a document indexing layer for the current lab document text records. A minimal first pass can use chunked text + keyword/vector-ready retrieval; multipart file upload can follow if needed.
3. Keep retrieval membership-scoped: onboarding answers must only use documents from labs the current user can access.
4. Add citations/source references to onboarding replies and assistant metadata so users can see which uploaded doc informed the answer.
5. Add regression tests:
   - same-lab document is retrieved for an onboarding question
   - other-lab document is not retrieved
   - answer includes source/citation metadata
   - onboarding still emits no part-design events and creates no artifacts

Secondary M8 items after M9 is unblocked:

- Smoke-test frontend Docker compose with real Clerk env.
- Decide whether object storage is required for the target deploy; local filesystem remains fine for single-instance dev.
- Managed Postgres migration plan.
- Re-check `npm audit --omit=dev`; current moderate PostCSS findings are through upstream Next/Clerk with no local fix available.
