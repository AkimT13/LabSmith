# M3 Contract — Chat-Based Design Sessions

**Status:** locked before parallel work begins. Changes require both backend and frontend agents to agree.

This document is the source of truth for the API surface between the M3 backend (FastAPI + SSE) and the M3 frontend (Next.js client). Both agents code against this. If something here is wrong or missing, **stop and fix this doc** instead of diverging implementations.

---

## 1. Goal

User opens a session at `/dashboard/sessions/[sessionId]`. They type a prompt like "make the wells deeper". The frontend POSTs to a chat endpoint that returns an SSE stream. The stream emits incremental assistant text, a parsed spec, validation issues, then a generated artifact. The frontend renders all of that live.

Backend persists every user + assistant message and every generated artifact, with versioning when the same session re-generates.

---

## 2. REST Endpoints

All routes require Clerk auth (`Authorization: Bearer <jwt>`) and use `get_current_user` + project-member authorization (already established in M2).

### `POST /api/v1/sessions/{session_id}/chat`

Initiate a chat turn. Returns a Server-Sent Events stream.

**Request:**
```json
{
  "content": "make the wells 5mm deeper",
  "metadata": {}                           // optional, freeform
}
```

**Response:** `Content-Type: text/event-stream` (see §3).

**Errors:**
- `401` — missing or invalid JWT
- `403` — current user is not a member of the session's lab
- `404` — session does not exist
- `409` — session status is `archived` (cannot post to archived sessions)
- `422` — empty content
- `429` — rate limit (TBD; backend may stub this for now)

The user message is persisted **before** the SSE stream starts. The assistant message is persisted **at** `message_complete`.

### `GET /api/v1/sessions/{session_id}/messages`

List all messages in a session, oldest first. Used to hydrate the chat panel on page load and after refresh.

**Response:**
```json
[
  {
    "id": "uuid",
    "session_id": "uuid",
    "role": "user" | "assistant" | "system",
    "content": "string",
    "metadata": {} | null,
    "created_at": "iso8601"
  }
]
```

### `GET /api/v1/sessions/{session_id}/artifacts`

List artifacts for a session, newest first.

**Response:**
```json
[
  {
    "id": "uuid",
    "session_id": "uuid",
    "message_id": "uuid" | null,
    "artifact_type": "stl" | "step" | "spec_json" | "validation_json",
    "file_path": "string" | null,
    "file_size_bytes": 12345 | null,
    "spec_snapshot": {} | null,
    "validation": {} | null,
    "version": 1,
    "created_at": "iso8601"
  }
]
```

### `GET /api/v1/artifacts/{id}/download`

Returns the artifact bytes with `Content-Disposition: attachment; filename="..."`. Out of M3 scope (lands in M4) but the route should be reserved.

### `GET /api/v1/artifacts/{id}/preview`

Returns raw STL bytes for the 3D viewer. M4 scope.

---

## 3. SSE Event Catalog

Standard SSE wire format:

```
event: <type>
data: <single-line JSON>

```

Each event is a single JSON object on the `data:` line. Multi-line `data:` is not used. Order of events for a successful chat turn:

```
text_delta   (0..N times)
spec_parsed  (1 time, optional — only if a spec was parseable)
generation_started   (1 time, optional — only if a spec was parseable)
generation_complete  (1 time, optional — only if generation succeeded)
message_complete     (1 time — always)
```

If the turn fails, an `error` event is sent and the stream closes.

### Events

| event | when | payload |
|-------|------|---------|
| `text_delta` | new chunk of assistant text from the LLM | `{ "message_id": "uuid", "delta": "string" }` |
| `spec_parsed` | LLM finished extracting a `PartRequest` from the prompt | `{ "part_request": PartRequest, "validation": ValidationIssue[] }` |
| `generation_started` | CAD pipeline kicked off (after spec passes validation) | `{ "template": "tube_rack" \| "gel_comb" }` |
| `generation_complete` | artifact saved, 3D ready | `{ "artifact_id": "uuid", "artifact_type": "stl", "file_size_bytes": 12345, "version": 1 }` |
| `message_complete` | assistant message persisted, stream closing | `{ "message_id": "uuid", "content": "string" }` |
| `error` | fatal error; stream closes after | `{ "code": "string", "detail": "string" }` |

### Frontend handling

- `text_delta`: append `delta` to the in-progress assistant message keyed by `message_id`. The first `text_delta` for a `message_id` creates the message in local state.
- `spec_parsed`: render `SpecCard` + `ValidationBadge`. Update `currentSpec` for the session.
- `generation_started`: show generating indicator on the SpecCard.
- `generation_complete`: refresh the artifact list (or insert directly), trigger the 3D viewer to load `/api/v1/artifacts/{artifact_id}/preview`.
- `message_complete`: finalize the assistant message; replace the optimistic streaming message with the persisted version (same `message_id`).
- `error`: show toast or inline error in the chat panel.

### Heartbeat

Backend SHOULD emit `:keepalive\n\n` every 15s if no real event is ready, to prevent proxies from closing the connection.

---

## 4. Shared Type Definitions

### `PartRequest`

Already defined in `backend/src/labsmith/models.py` (Pydantic). Mirror in `frontend/src/lib/api.ts` as TypeScript:

```ts
export type PartType =
  | "tube_rack"
  | "gel_comb"
  | "multi_well_mold"
  | "microfluidic_channel_mold";

export interface PartRequest {
  part_type: PartType;
  source_prompt: string | null;
  rows: number | null;
  cols: number | null;
  well_count: number | null;
  diameter_mm: number | null;
  spacing_mm: number | null;
  depth_mm: number | null;
  well_width_mm: number | null;
  well_height_mm: number | null;
  tube_volume_ml: number | null;
  notes: string[];
}
```

### `ValidationIssue`

```ts
export interface ValidationIssue {
  severity: "error" | "warning";
  code: string;
  message: string;
  field: string | null;
}
```

### `Message`

```ts
export interface Message {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}
```

### `Artifact`

```ts
export type ArtifactType = "stl" | "step" | "spec_json" | "validation_json";

export interface Artifact {
  id: string;
  session_id: string;
  message_id: string | null;
  artifact_type: ArtifactType;
  file_path: string | null;
  file_size_bytes: number | null;
  spec_snapshot: Record<string, unknown> | null;
  validation: Record<string, unknown> | null;
  version: number;
  created_at: string;
}
```

---

## 5. Backend Implementation Plan

- New router: `backend/app/routers/chat.py`
- New router: `backend/app/routers/messages.py` (list)
- New router: `backend/app/routers/artifacts.py` (list + download/preview shells; bodies in M4)
- New service: `backend/app/services/chat.py` — orchestrates: persist user msg → call LLM parser → emit events → run CAD pipeline → persist artifact → persist assistant msg
- New schemas: `backend/app/schemas/chat.py`, `backend/app/schemas/messages.py`, `backend/app/schemas/artifacts.py`
- Reuse from `backend/src/labsmith/`: `RuleBasedParser`, templates, validation, export
- For M3, the LLM parser can wrap the rule-based parser (so we ship without an LLM dependency). Replace with real OpenAI call later.

### Mock mode

Backend agent: ship `LABSMITH_CHAT_MOCK=true` env flag. When set, `chat_service` emits scripted events with `asyncio.sleep` between them — no LLM, no CadQuery — so the frontend agent can develop against a real-looking stream without backend secrets. Default off.

The mock should emit:
1. 5 × `text_delta` over ~1s
2. 1 × `spec_parsed` (using the rule-based parser on the user's prompt — that already works)
3. 1 × `generation_started`
4. 1 × `generation_complete` (with a fake artifact_id and file_size_bytes)
5. 1 × `message_complete`

This gives the frontend a deterministic stream to test against.

### Tests

- `backend/tests/test_chat_api.py` — unit tests for chat service (mock LLM); integration tests for SSE event ordering using `httpx.AsyncClient` + parsing the event stream.

---

## 6. Frontend Implementation Plan

- New file: `frontend/src/lib/use-chat.ts` — React hook that wraps `fetch` with `ReadableStream` parsing for SSE. (Don't use `EventSource` — it doesn't support custom headers, so we can't send the Clerk Bearer token. Use `fetch` + `response.body.getReader()`.)
- New components in `frontend/src/components/sessions/`:
  - `chat-panel.tsx` — message list + input
  - `message-bubble.tsx`
  - `spec-card.tsx`
  - `validation-badge.tsx`
  - `artifact-list.tsx` (M3 reads list; M4 wires the 3D viewer)
- Update `frontend/src/app/(dashboard)/dashboard/sessions/[sessionId]/page.tsx` — replace the M2.4 placeholder card with the chat panel + an empty viewer panel.
- Update `frontend/src/lib/api.ts` — add `Message`, `Artifact`, `PartRequest`, `ValidationIssue` types and `fetchMessages`, `fetchArtifacts`, `postChat` (the postChat helper returns the raw stream; the hook does the parsing).

### SSE parsing reference

```ts
const response = await fetch(`/api/v1/sessions/${sessionId}/chat`, {
  method: "POST",
  headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
  body: JSON.stringify({ content }),
});
const reader = response.body!.getReader();
const decoder = new TextDecoder();
let buffer = "";
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const events = buffer.split("\n\n");
  buffer = events.pop() ?? "";
  for (const block of events) {
    // parse "event: X\ndata: {...}"
  }
}
```

---

## 7. Coordination

- **Branches**: `m3-backend` and `m3-frontend`. Final integration via PR.
- **Shared files** that will conflict if both touch them:
  - `frontend/src/lib/api.ts` — add types here. **Frontend agent owns this file.** Backend agent must not edit it. Backend agent posts new types to the contract; frontend agent transcribes them into `api.ts`.
  - `PROGRESS.md` — both agents will update this. Last to merge takes the conflict and reconciles.
  - `frontend/src/app/(dashboard)/dashboard/sessions/[sessionId]/page.tsx` — owned by frontend agent.
- **Commit cadence**: per-agent branch, commit at clean checkpoints (passing tests, working component), push incrementally.
- **Sync points**:
  1. Day 1 end: backend ships mock-mode endpoint + types frozen. Frontend can start.
  2. Mid-milestone: backend implements real parser (rule-based wrapper for now); frontend connects.
  3. End: integration test together against real backend.

---

## 8. Out of scope for M3

Mentioned here so neither agent accidentally builds them:

- Real LLM integration (OpenAI). M3 ships with rule-based parser wrapped to emit text deltas. LLM swap is a small later change.
- Real CadQuery export. M3 generates artifact rows but `file_path` may be null or point to a placeholder. **Real STL bytes land in M5**, 3D viewer in M4.
- Rate limiting on `/chat`. Stub for now.
- Artifact download/preview endpoint bodies (M4).
