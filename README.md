# LabSmith

LabSmith is a full-stack scaffold for LabForge AI: an autonomous design agent that turns natural-language laboratory hardware requests into structured CAD generation plans.

The first implementation target is simple, parametric lab hardware such as tube racks, gel electrophoresis combs, and general multi-well molds. The backend owns parsing, validation, CAD template selection, and future STL/STEP export. The frontend owns the interactive TypeScript user experience.

## Repository layout

```text
.
├── backend/
│   ├── src/labsmith/
│   │   ├── export/          # STL/STEP export boundary
│   │   ├── parser/          # Prompt-to-parameters adapters
│   │   ├── templates/       # Parametric CAD template registry
│   │   ├── validation/      # Manufacturability checks
│   │   ├── main.py          # FastAPI app
│   │   └── models.py        # API/domain models
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── api/             # Typed API client and DTOs
│   │   ├── components/      # React UI components
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── vite.config.ts
├── package.json             # Root workspace scripts
└── pyproject.toml           # Python package and tooling config
```

## Architecture

```text
User prompt
  -> parser
  -> structured PartRequest
  -> template registry
  -> validation rules
  -> estimated dimensions
  -> planned STL/STEP exports
```

CadQuery integration is intentionally isolated behind `backend/src/labsmith/export/`. The current scaffold returns export plans instead of writing files, so the API and UI can be developed before the CAD engine is installed and hardened.

## Local setup

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
npm run backend:dev
```

The API runs at `http://localhost:8000`.

Use `npm run backend:dev:reload` when your environment supports file watching.

Useful endpoints:

- `GET /health`
- `GET /templates`
- `POST /parse`
- `POST /design`

### Frontend

```bash
npm install
npm run frontend:dev
```

The Vite app runs at `http://localhost:5173` and calls the backend at `http://localhost:8000` by default. Override with `VITE_API_BASE_URL` when needed.

## Current supported templates

- Tube rack
- Gel electrophoresis comb
- General multi-well mold

The broader product roadmap still includes multi-well molds and basic microfluidic channel molds, but those templates are not registered until the geometry and validation rules are defined.

## Example prompts

```text
Create a multi-well mold with 96 wells, 1 mm diameter, 2 mm spacing
Design a rack for 1.5 mL tubes that fits in a standard ice bucket
Make a gel electrophoresis comb with 10 wells
```

## Verification

```bash
npm run backend:test
npm run frontend:check
```

## Product vision

LabSmith adds a missing tool-creation step to the scientific workflow:

```text
Hypothesis -> Experiment Design -> Tool Creation -> Execution -> Analysis
```

The long-term goal is to let labs produce simple, validated, fabrication-ready hardware on demand instead of relying on expensive niche suppliers or manual CAD work.
