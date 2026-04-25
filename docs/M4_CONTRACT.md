# M4 Contract — 3D Preview + File Downloads

**Status:** locked before parallel work begins. Same rules as M3: if something here is wrong or missing, fix this doc instead of letting implementations diverge.

This pins the API surface between the M4 backend (artifact storage + download/preview routes) and the M4 frontend (3D STL viewer + download buttons). Both agents code against this; final integration is via PR.

---

## 1. Goal

When the chat pipeline finishes a turn, the artifact list refreshes and the 3D viewer renders the resulting STL inline. Users can rotate/zoom the model and click a download button to save STL/STEP files locally.

End state for M4 (before M5 plugs in real CadQuery):
- The backend ships a storage abstraction with a local-filesystem default, plus a mock-mode placeholder so the viewer has *something* to render even before real CAD lands.
- `GET /api/v1/artifacts/{id}/download` and `GET /api/v1/artifacts/{id}/preview` return real bytes.
- The frontend session page has a viewer panel next to the chat panel that auto-refreshes on `generation_complete`.

---

## 2. Storage Abstraction

The `Artifact.file_path` column stores a **storage key**, not an absolute filesystem path. The storage backend resolves keys to bytes. This keeps S3/Spaces/whatever swap-in later as a one-class change.

### Key scheme

```
sessions/<session_id>/artifacts/<artifact_id>.<ext>
```

Example: `sessions/3a91.../artifacts/0468.../v1.stl`

The version is folded into the filename so re-generation creates new files instead of clobbering. The exact filename format is a backend implementation detail — the frontend only ever sees artifact IDs and uses them in URLs. Don't rely on filename shape from the frontend side.

### `StorageBackend` protocol

```python
# backend/app/services/storage.py

class StorageBackend(Protocol):
    async def save(self, key: str, data: bytes, *, content_type: str) -> StorageObject: ...
    async def read(self, key: str) -> bytes: ...
    async def exists(self, key: str) -> bool: ...
    async def delete(self, key: str) -> None: ...

@dataclass
class StorageObject:
    key: str
    size_bytes: int
    content_type: str
```

### `LocalFilesystemStorage`

- Reads `LABSMITH_STORAGE_DIR` from settings (default: `./backend/storage`).
- Resolves keys to `<storage_dir>/<key>`.
- Creates parent directories on save.
- The directory is in `.gitignore`.

### Configuration

```
LABSMITH_STORAGE_BACKEND=local        # only "local" supported in M4
LABSMITH_STORAGE_DIR=./backend/storage
```

---

## 3. REST Endpoints

All routes require Clerk auth (`Authorization: Bearer <jwt>`) and lab-membership on the artifact's session (same rule as M3). Reuse `_resolve_artifact()` from the existing `app/routers/artifacts.py`.

### `GET /api/v1/artifacts/{id}/download`

Returns the artifact bytes as a downloadable attachment.

**Response headers:**
```
Content-Type: <artifact mime type>
Content-Disposition: attachment; filename="<sanitized session title>-v<version>.<ext>"
Content-Length: <size>
Cache-Control: private, no-cache
```

**Body:** raw artifact bytes.

**Errors:**
- `401` — missing/invalid JWT
- `403` — caller is not a lab member of the artifact's session
- `404` — artifact not found, OR `file_path` is null, OR file is missing on disk
- `415` — artifact_type doesn't have a download surface (reserved; M4 supports stl/step)

The filename should be safe to put in `Content-Disposition`. Use ASCII fallback + RFC 5987 `filename*=UTF-8''...` for non-ASCII titles. A simple slugify of the session title is fine.

### `GET /api/v1/artifacts/{id}/preview`

Returns the same bytes inline (no `Content-Disposition`), suitable for the 3D viewer to load via `fetch()` + `arrayBuffer()`.

**Response headers:**
```
Content-Type: <artifact mime type>
Content-Length: <size>
Cache-Control: private, max-age=300
ETag: "<artifact_id>:v<version>"
```

**Body:** raw artifact bytes.

**Errors:** same as `download`.

The frontend MUST send the ETag back as `If-None-Match` on subsequent requests for the same artifact; backend responds `304 Not Modified` to avoid re-shipping bytes the browser already has.

### Existing endpoints unchanged

- `GET /api/v1/sessions/{session_id}/artifacts` — already shipped in M3, returns `Artifact[]`. M4 adds a `file_url` field (see §4).

### MIME type mapping

| `artifact_type` | `Content-Type`              | Extension |
|-----------------|------------------------------|-----------|
| `stl`           | `model/stl`                  | `.stl`    |
| `step`          | `model/step` *(or `application/step` — pick one and stick to it)* | `.step`   |
| `spec_json`     | `application/json`           | `.json`   |
| `validation_json` | `application/json`         | `.json`   |

Backend agent: pick `model/step` and document it. Frontend can treat all of these as opaque blobs — it only special-cases `stl` for 3D rendering.

---

## 4. Artifact Schema Update

`Artifact` rows in M3 already have `file_path`, `file_size_bytes`, `version`. M4 adds **derived URL fields** to the response shape so the frontend doesn't have to construct URLs by hand:

```ts
export interface Artifact {
  id: string;
  session_id: string;
  message_id: string | null;
  artifact_type: ArtifactType;
  file_path: string | null;        // storage key, opaque to frontend
  file_size_bytes: number | null;
  spec_snapshot: Record<string, unknown> | null;
  validation: Record<string, unknown> | null;
  version: number;
  created_at: string;

  // NEW in M4:
  download_url: string | null;     // e.g. /api/v1/artifacts/{id}/download, null if file_path is null
  preview_url: string | null;      // null if artifact_type !== "stl" or file_path is null
}
```

The Pydantic `ArtifactResponse` computes these fields server-side. The frontend never builds these URLs by hand — if the backend says null, there's no preview/download.

`preview_url` returning null lets the viewer cleanly show the empty-state for non-STL or unbuilt artifacts.

---

## 5. Mock Mode Behavior

`LABSMITH_CHAT_MOCK=true` (the default) has been generating Artifact rows with `file_path=None`. M4 changes this:

When mock mode runs, `_run_generation` SHOULD write a small placeholder STL to storage and populate `file_path` + `file_size_bytes` correctly. This way the frontend viewer has real bytes to render before M5 ships real CadQuery output.

**Placeholder STL choice:** a 10 mm unit cube in binary STL format (~684 bytes). Backend agent ships it as a constant in `app/services/chat.py` or a static asset.

The placeholder is identical for every generation in mock mode — that's fine. Real CadQuery in M5 replaces the byte source while `_run_generation` keeps the same persistence shape.

If `LABSMITH_CHAT_MOCK=false` and no real CAD provider is configured, generation still produces an Artifact row but with `file_path=None`. Frontend treats that gracefully (empty viewer, disabled download button).

---

## 6. Frontend Implementation Plan

### New dependencies

```
npm install three @types/three @react-three/fiber @react-three/drei
```

`drei`'s `useLoader` + `STLLoader` from `three/examples/jsm/loaders/STLLoader` is the canonical pattern. The viewer is a client component.

### New files

```
frontend/src/components/sessions/
  stl-viewer.tsx          # <Canvas> + STLLoader, orbit controls, grid, lighting
  viewer-panel.tsx        # wraps stl-viewer with empty/loading/error states
```

### Updated files

- `frontend/src/components/sessions/artifact-list.tsx` — add download button (`<a href={artifact.download_url} download>` is enough; no JS needed). Disable when `download_url` is null.
- `frontend/src/app/(dashboard)/dashboard/sessions/[sessionId]/page.tsx` — replace the placeholder card from M2.4 with a split layout: chat panel (left) + viewer panel (right). On `generation_complete` the page already calls `loadArtifacts()` (it does today via `onArtifactGenerated`). The viewer panel rerenders when the most-recent STL artifact changes.
- `frontend/src/lib/api.ts` — add `download_url` and `preview_url` to the `Artifact` type. No new fetcher needed; the viewer fetches `preview_url` directly with `fetch()`.

### Viewer behavior contract

- **Empty state** (`preview_url` is null): "Generate a part to see the 3D preview here."
- **Loading state**: spinner overlay while `fetch(preview_url)` is in flight.
- **Error state**: "Couldn't load preview. <retry button>".
- **Loaded**: `<Canvas>` with the STL geometry, OrbitControls, a grid floor, ambient + directional light, default camera at distance ~3× the model's bounding-sphere radius.
- **ETag respect**: re-fetching the same `preview_url` after `generation_complete` should not re-download identical bytes — pass `If-None-Match` if the browser doesn't already (it usually does for same-origin GETs).

### Lazy load

Three.js is large (~600KB). Wrap the viewer with `next/dynamic`:

```tsx
const StlViewer = dynamic(() => import("@/components/sessions/stl-viewer"), {
  ssr: false,
  loading: () => <ViewerLoadingSkeleton />,
});
```

This keeps the initial dashboard bundle small.

---

## 7. Backend Implementation Plan

### New files
- `backend/app/services/storage.py` — `StorageBackend` protocol + `LocalFilesystemStorage`
- `backend/app/services/storage_factory.py` *(or just a `get_storage()` function in storage.py)* — reads settings, returns the right backend
- A constant or static asset `backend/app/assets/placeholder.stl` for mock mode

### Updated files
- `backend/app/config.py` — add `storage_backend`, `storage_dir` settings
- `backend/app/services/chat.py` — `_run_generation` writes the placeholder STL via the storage backend in mock mode, sets `file_path` to the returned key
- `backend/app/routers/artifacts.py` — fill in `download` and `preview` bodies (currently 501)
- `backend/app/schemas/artifacts.py` — add computed `download_url` and `preview_url` fields

### Tests
- `backend/tests/test_storage.py` — local filesystem save/read/delete roundtrip with a temp dir
- `backend/tests/test_artifact_endpoints.py` — verify download returns bytes with correct headers, preview returns inline, both 404 when file_path is null, both 403 for non-members
- Existing `test_chat_api.py` — update assertions to confirm mock generation now produces non-null `file_path` and `file_size_bytes` matching the placeholder STL size

---

## 8. Coordination

- **Branches**: `m4-backend` (this machine, me) and `m4-frontend` (teammate).
- **Shared files** that will conflict if both touch:
  - `frontend/src/lib/api.ts` — frontend agent owns; backend posts type changes here for transcription.
  - `PROGRESS.md` — same rule as M3, last to merge reconciles.
  - `frontend/src/components/sessions/artifact-list.tsx` — frontend agent owns.
  - `frontend/src/app/(dashboard)/dashboard/sessions/[sessionId]/page.tsx` — frontend agent owns.
- **Sync points**:
  1. Day-1: backend ships `download` + `preview` route bodies + mock placeholder STL. Frontend can start building the viewer against real bytes.
  2. Mid-milestone: frontend connects, both agents check that `If-None-Match` / `ETag` actually skip re-downloads.
  3. End: integration test together. Run `npm run frontend:build`, `npm run backend:test`, manual smoke with chat → generate → preview → download.

---

## 9. Out of scope for M4

Mentioned so neither agent accidentally builds them:

- **Real CadQuery output.** M5. M4's mock mode ships a unit cube; M5 swaps in real geometry.
- **S3 / object storage backend.** Storage abstraction is shaped for it, but only the local filesystem implementation lands in M4.
- **STEP file viewer.** Three.js doesn't render STEP. Download is supported, preview is null for STEP artifacts.
- **Streaming uploads / multipart range requests.** Whole-file responses only. Re-evaluate if files exceed ~50MB in practice.
- **Real LLM streaming.** Still mock; the LLM provider abstraction (commit `32ee189` on `m3_akim`) is stranded and unrelated to M4.
- **Authorization beyond lab membership.** No per-artifact ACLs.

---

## 10. Quick reference for frontend-side fetching

```ts
// inside <StlViewer> when preview_url changes
const response = await fetch(artifact.preview_url, {
  credentials: "include",
  headers: { Authorization: `Bearer ${token}` },
});
if (!response.ok) throw new Error(`Preview failed: ${response.status}`);
const buffer = await response.arrayBuffer();
const geometry = stlLoader.parse(buffer);
// ... feed into <mesh geometry={geometry} />
```

Authorization: the same Clerk Bearer token used everywhere else. The backend treats `download` and `preview` like any other authenticated route — credentials are required even for "download" links, so a plain `<a href="...">` from the frontend won't work without injecting the header. Two options:

- **Option A (recommended)**: download button does `fetch(...) → blob → URL.createObjectURL → <a download>`. ~10 lines.
- **Option B**: backend returns short-lived signed URLs for download. More setup, defer to post-M4.

M4 ships Option A. Frontend agent: implement the download click handler in `artifact-list.tsx` to fetch the bytes and trigger a download via blob URL.
