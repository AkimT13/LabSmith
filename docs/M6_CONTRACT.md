# M6 Contract - Real CadQuery Generation

**Status:** draft contract for the next implementation milestone.

M6 replaces the M4/M5 placeholder STL path with real CadQuery-generated
geometry for `part_design` sessions. It must preserve the M4 storage,
download, preview, and frontend viewer contracts.

## 1. Goal

For valid supported `part_design` prompts, the backend should save real CAD
bytes instead of the placeholder cube.

Supported generated templates in M6:

| Part type | Required in M6 |
|---|---:|
| `tube_rack` | yes |
| `gel_comb` | yes |

M6 must not add new product families. It should only make the existing supported
part types generate real geometry.

## 2. Non-Goals

M6 does not require:

- frontend viewer changes
- new artifact routes
- object storage
- a real LLM parser
- onboarding-agent implementation
- freeform CAD generation
- browser STEP preview

## 3. Existing Boundaries To Preserve

M6 must preserve:

- `POST /api/v1/sessions/{session_id}/chat`
- the `part_design` SSE event catalog from M5
- `GET /api/v1/sessions/{session_id}/artifacts`
- `GET /api/v1/artifacts/{artifact_id}/download`
- `GET /api/v1/artifacts/{artifact_id}/preview`
- `ArtifactResponse.download_url`
- `ArtifactResponse.preview_url`
- storage key shape:

```text
sessions/<session_id>/artifacts/<artifact_id>-v<version>.<ext>
```

The frontend should continue loading authenticated STL bytes through
`preview_url` with the Clerk Bearer token.

## 4. Artifact Requirements

### STL

STL is required for M6.

For each successful generation:

- create an `Artifact` row with `artifact_type="stl"`
- save real STL bytes through `StorageBackend`
- set `file_path`
- set `file_size_bytes`
- set `spec_snapshot`
- set `validation`
- emit `generation_complete`

The STL bytes must not equal `get_placeholder_stl_bytes()`.

### STEP

STEP is optional for M6. If implemented, create a second artifact with
`artifact_type="step"` and a `.step` storage key.

If STEP is not implemented in M6, do not fake it and do not create placeholder
STEP artifacts.

## 5. Mock Mode Change

Before M6, `settings.chat_mock=true` also caused generation to save a
placeholder STL.

After M6:

- `chat_mock` may keep the scripted assistant text and cosmetic delays.
- Real CadQuery generation should run for valid supported specs by default.
- If a CAD mock escape hatch is still needed, introduce a separate setting such
  as `LABSMITH_CAD_MOCK=true`.

The default local dev experience should show real tube-rack or gel-comb
geometry once M6 lands.

## 6. Generation Location

Primary integration point:

```text
backend/app/services/agents/part_design.py
```

The current `_run_generation()` function should call a CAD generation service
instead of directly loading placeholder bytes.

Recommended new service boundary:

```text
backend/app/services/cad_generation.py
```

Suggested interface:

```python
@dataclass(frozen=True)
class GeneratedCadArtifact:
    artifact_type: ArtifactType
    extension: str
    content_type: str
    data: bytes

async def generate_cad_artifacts(part_request: PartRequest) -> list[GeneratedCadArtifact]:
    ...
```

CadQuery work is CPU-bound and should not block the event loop. Run it through:

```python
await asyncio.to_thread(...)
```

## 7. Template Behavior

### Tube Rack

Inputs:

- `rows`
- `cols`
- `diameter_mm`
- `spacing_mm`
- optional `depth_mm`
- optional `tube_volume_ml`

Parser/default behavior already supplies:

- default layout: `4 x 6` when unspecified
- diameter from known tube volume when possible
- spacing default: `diameter_mm + 4.0`

Validation already requires:

- rows
- columns
- diameter
- spacing
- spacing at least `diameter_mm + 0.4`

Geometry expectation:

- rectangular rack or plate
- repeated cylindrical openings in a grid
- dimensions roughly match requested rows, columns, diameter, and spacing
- model centered or positioned predictably for viewer display
- no overlapping openings after validation passes

Suggested default height:

```text
depth_mm if provided, otherwise 20.0 mm
```

### Gel Comb

Inputs:

- `well_count`
- `well_width_mm`
- `well_height_mm`
- `depth_mm`
- optional `spacing_mm`

Parser/default behavior already supplies:

- default well count: `10`
- default well width: `5.0 mm`
- default tooth thickness: `1.5 mm`
- default tooth depth: `8.0 mm`

Geometry expectation:

- top rail
- repeated teeth
- tooth count equals `well_count`
- width/depth roughly match requested values
- model centered or positioned predictably for viewer display

Suggested default spacing:

```text
2.0 mm
```

## 8. Error Behavior

Parser and validation behavior stays unchanged:

- unparseable prompt: no `spec_parsed`, no generation
- validation errors: `spec_parsed` with errors, no generation

CAD failures:

- should emit one `error` SSE event through the dispatcher
- should not emit `generation_complete`
- should not leave an artifact row pointing to missing bytes
- should log enough context for debugging without exposing secrets

If partial rows are created before byte generation completes, roll back on
failure.

## 9. Tests

Backend tests should add coverage for:

- tube rack generation creates real STL bytes
- gel comb generation creates real STL bytes
- generated STL bytes differ from placeholder cube bytes
- generated STL bytes have a valid STL structure
- artifact `file_size_bytes` matches saved bytes
- artifact `preview_url` and `download_url` still work
- invalid spacing blocks generation and creates no artifact
- repeated generation increments versions and writes distinct storage keys

Dimension tests should parse the generated STL enough to verify bounding boxes
within practical tolerance. A small local STL parser in tests is acceptable and
keeps the test suite independent of viewer code.

Suggested commands:

```bash
npm run backend:test
npm --prefix frontend run lint
npm --prefix frontend run build
```

## 10. Manual Acceptance

With backend and frontend running:

```bash
npm run backend:dev
npm run frontend:dev
```

In a `part_design` session, send:

```text
Create a 4 x 6 tube rack with 11 mm diameter and 15 mm spacing.
```

Expected:

- spec parses as `tube_rack`
- validation passes
- artifact list refreshes
- STL viewer shows a rack-like object, not a cube
- retry reloads without error
- download saves a real STL

Then send:

```text
Make a gel electrophoresis comb with 10 wells.
```

Expected:

- spec parses as `gel_comb`
- validation passes
- artifact list refreshes
- STL viewer shows a comb-like object, not a cube
- download saves a real STL

