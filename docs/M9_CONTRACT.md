# M9 Contract - Onboarding Agent

## 1. Goal

M9 replaces the M5 onboarding placeholder with a useful onboarding assistant
for lab orientation. It should help a new lab member understand where to start,
what to ask next, and which lab/project context matters.

The first implementation is intentionally deterministic. It supports lab-scoped
text document storage and document metadata awareness, but it does not use
OpenAI, embeddings, semantic retrieval, or citations yet.

## 2. Ownership Boundaries

### Onboarding lane owns

- `backend/app/services/agents/onboarding.py`
- onboarding event catalog and tests
- onboarding-only frontend copy or UI surfaces
- lab document metadata/upload endpoints
- this contract and M9 progress notes

### File-maker/CAD lane owns

- part-design CAD generation
- STL/STEP/export work
- artifact storage/download/viewer behavior
- CAD parser/spec extraction behavior

### Shared files require care

- `backend/app/services/chat.py`
- `backend/app/services/agents/base.py`
- `backend/app/services/agents/registry.py`
- `frontend/src/lib/use-chat.ts`
- session creation/type UI

M9 onboarding must not change the part-design event catalog or create
artifacts.

## 3. Onboarding Agent Behavior

### v0 deterministic behavior

For each onboarding chat turn, the agent should:

- classify the user's question into an onboarding topic
- produce a concise answer with lab/project/session context when available
- include a practical checklist
- mention available lab document records when they exist
- make clear that semantic search and citations are not connected yet
- suggest concrete follow-up questions
- persist one assistant message
- create no artifacts

Supported v0 topics:

- `getting_started`
- `protocols`
- `equipment`
- `safety`
- `people`
- `access`
- `data`

### Future behavior

Later M9 or M10 work may add:

- multipart document upload
- document chunking/indexing
- membership-aware semantic retrieval
- citations to specific uploaded documents
- checklist persistence
- onboarding-specific frontend panels

## 4. Event Catalog

The onboarding agent may emit:

```json
{"event": "topic_suggested", "data": {"topic": "equipment", "label": "Equipment and locations", "rationale": "Matched equipment/location terms."}}
```

```json
{"event": "checklist_step", "data": {"step_id": "equipment-1", "title": "Find the current owner", "detail": "Ask who maintains the equipment and who can train you.", "status": "suggested"}}
```

```json
{"event": "doc_referenced", "data": {"title": "SOP title", "source": "uploaded document", "url": null}}
```

```json
{"event": "text_delta", "data": {"message_id": "<uuid>", "delta": "partial text"}}
```

```json
{"event": "message_complete", "data": {"message_id": "<uuid>", "content": "final assistant message"}}
```

`doc_referenced` is reserved for document-backed work and should not be emitted
until the agent actually reads or retrieves from document contents. Seeing
document metadata alone is not enough.

Forbidden onboarding events:

- `spec_parsed`
- `generation_started`
- `generation_complete`

## 5. Persistence Rules

- The user message is persisted by the shared chat preflight.
- The onboarding agent persists exactly one assistant message per turn.
- Assistant message metadata should include the selected onboarding topic.
- Lab document metadata is scoped to a laboratory and protected by lab
  membership.
- Text document bytes are stored through the existing `StorageBackend`; the API
  never exposes storage keys.
- The onboarding agent must not create `Artifact` rows.

## 6. Verification

Required backend checks:

```bash
npm run backend:test
```

Focused checks:

```bash
python3 -m pytest backend/tests/test_agents.py
python3 -m ruff check backend/app/services/agents/onboarding.py backend/tests/test_agents.py
```

Frontend checks are required only when frontend files change:

```bash
npm run frontend:lint
npm run frontend:build
```
