# M5 Contract - Session Types + Agent Abstraction

**Status:** retroactively locked after PR #4 (`m5_akim`) landed on `main`.

M5 inserted a session-type and agent-dispatch layer between the generic chat
route and the per-session behavior. It did not change the M4 artifact storage,
download, or preview contract.

## 1. Goal

Support multiple chat session types without forking the chat router or frontend
stream parser.

M5 ships two session types:

| Session type | Backend enum | Agent | Status |
|---|---|---|---|
| `part_design` | `SessionType.PART_DESIGN` | `PartDesignAgent` | Existing M3/M4 design flow |
| `onboarding` | `SessionType.ONBOARDING` | `OnboardingAgent` | Placeholder stub in M5; M9 owns the real implementation |

`part_design` remains the only session type that parses a part spec or creates
artifacts in M5.

## 2. Data Model

`design_sessions` has a required `session_type` column.

Postgres stores enum names:

```text
PART_DESIGN
ONBOARDING
```

The API serializes lower-case string enum values:

```json
"part_design"
"onboarding"
```

### Migration

Alembic revision:

```text
backend/alembic/versions/b6d58704dee5_add_session_type_to_design_sessions.py
```

The migration:

- creates the Postgres enum type `session_type`
- adds `design_sessions.session_type`
- backfills existing sessions to `PART_DESIGN`
- leaves the Python model named `DesignSession`

Run after pulling M5:

```bash
npm run backend:migrate
```

## 3. Session API

### Create

`POST /api/v1/projects/{project_id}/sessions`

Accepts:

```json
{
  "title": "Agent session",
  "session_type": "part_design",
  "part_type": "tube_rack",
  "current_spec": null
}
```

Rules:

- `session_type` is optional.
- Default is `part_design`.
- `part_type` is meaningful only for `part_design`.
- `onboarding` sessions should generally omit `part_type`.

### Read

Session responses include:

```json
{
  "session_type": "part_design"
}
```

### Update

`PATCH /api/v1/sessions/{session_id}` does not accept `session_type`.

`session_type` is immutable because existing message history was produced under
that session's agent rules and event catalog. To change the type, create a new
session.

## 4. Agent Protocol

Agents implement `SessionAgent`:

```python
async def run_turn(
    *,
    db: AsyncSession,
    session: DesignSession,
    user: User,
    user_content: str,
) -> AsyncGenerator[AgentEvent, None]:
    ...
```

Agent events are dictionaries:

```python
{"event": "<event_type>", "data": {...}}
```

The chat router serializes these dictionaries as Server-Sent Events. The router
does not know session-type-specific behavior.

### Caller Guarantees

Before an agent runs, `prepare_chat_turn()` has already:

- verified auth and lab membership
- rejected archived sessions with `409`
- persisted the user message
- committed the user message

### Agent Responsibilities

Each agent owns:

- its event catalog
- assistant message persistence
- artifact persistence, if any
- successful transaction commit

Unhandled agent exceptions are converted by the dispatcher into a single
`error` SSE event.

## 5. Registry

`app/services/agents/registry.py` maps `SessionType` to singleton agent
instances.

Current registry:

```python
{
    SessionType.PART_DESIGN: PartDesignAgent(),
    SessionType.ONBOARDING: OnboardingAgent(),
}
```

Every `SessionType` value must have a registered agent. Missing registrations
are programming errors and should fail loudly.

## 6. Event Catalogs

### `part_design`

This is the existing M3/M4 design flow behind `PartDesignAgent`.

Events:

| Event | Count | Payload | Notes |
|---|---:|---|---|
| `text_delta` | `0..N` | `{ "message_id": "uuid", "delta": "string" }` | Streams assistant text |
| `spec_parsed` | `0..1` | `{ "part_request": PartRequest, "validation": ValidationIssue[] }` | Only when parsing succeeds |
| `generation_started` | `0..1` | `{ "template": "tube_rack" \| "gel_comb" }` | Only when validation has no errors |
| `generation_complete` | `0..1` | `{ "artifact_id": "uuid", "artifact_type": "stl", "file_size_bytes": number, "version": number }` | Only when artifact bytes are saved |
| `message_complete` | `1` | `{ "message_id": "uuid", "content": "string" }` | Final event on normal completion |
| `error` | `0..1` | `{ "code": "string", "detail": "string" }` | Emitted by dispatcher on unhandled exceptions |

Validation errors stop before generation. Unparseable prompts emit
`message_complete` only after text streaming.

M5 still uses the M4 placeholder STL in mock-mode generation. Real geometry is
M6.

### `onboarding`

This is the M5 stub contract. M9 replaces it with the real onboarding catalog
in `docs/M9_CONTRACT.md`. It must not emit design-only events.

Events:

| Event | Count | Payload | Notes |
|---|---:|---|---|
| `text_delta` | `1..N` | `{ "message_id": "uuid", "delta": "string" }` | Streams placeholder reply |
| `message_complete` | `1` | `{ "message_id": "uuid", "content": "string" }` | Final event |
| `error` | `0..1` | `{ "code": "string", "detail": "string" }` | Emitted by dispatcher on unhandled exceptions |

Forbidden for `onboarding` in M5:

- `spec_parsed`
- `generation_started`
- `generation_complete`
- artifact creation

## 7. Frontend Contract

Frontend types:

```ts
export type SessionType = "part_design" | "onboarding";
```

Create mode shows a session-type picker. Edit mode hides it because
`session_type` is immutable.

Session detail routing:

- `part_design`: existing chat + artifact list + STL viewer layout
- `onboarding`: chat-only layout with preview notice

The existing `useChat` hook handles both current event catalogs. No new frontend
event handlers are required for the M5 onboarding stub.

## 8. Test Requirements

Backend tests must cover:

- registry returns `PartDesignAgent` for `part_design`
- registry returns `OnboardingAgent` for `onboarding`
- create defaults to `part_design`
- create with `onboarding` persists and round-trips
- patch cannot mutate `session_type`
- `part_design` still emits the M3/M4 design event sequence
- `onboarding` emits only `text_delta` and `message_complete`
- `onboarding` creates no artifacts

Verification command:

```bash
npm run backend:test
```

Frontend verification:

```bash
npm --prefix frontend run lint
npm --prefix frontend run build
```

## 9. Adding A New Agent

To add a session type:

1. Add the value to `SessionType`.
2. Add an Alembic migration for the Postgres enum.
3. Implement `SessionAgent`.
4. Register it in `app/services/agents/registry.py`.
5. Document the event catalog here or in the milestone contract that owns it.
6. Add tests for routing, persistence, and event catalog boundaries.
