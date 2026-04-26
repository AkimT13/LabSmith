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
│   │   ├── app/             # Next.js App Router pages/layouts
│   │   ├── components/      # React UI components
│   │   └── lib/             # Typed API client and browser helpers
│   └── next.config.ts
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
  -> CadQuery STL generation
  -> persisted/downloadable artifacts
```

CadQuery integration is isolated behind `backend/app/services/cad_generation.py` and the parametric templates under `backend/src/labsmith/templates/`. The current artifact path produces STL files for supported part-design sessions.

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

The Next.js app runs at `http://localhost:3000` and calls the backend at `http://localhost:8000` by default. Override with `NEXT_PUBLIC_API_BASE_URL` when needed.

### Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Compose starts Postgres, runs Alembic migrations before the backend starts, and serves:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Postgres: `localhost:5432`

Set real Clerk values in `.env` before using authenticated dashboard routes.

The backend service is pinned to `linux/amd64` because CadQuery/OCP currently does not publish Linux ARM64 wheels. On Apple Silicon, Docker Desktop runs that container through emulation.

If local services already occupy the default ports, override `POSTGRES_PORT`, `BACKEND_PORT`, or `FRONTEND_PORT` in `.env`.

## Current supported templates

- Tube rack
- Gel electrophoresis comb
- Real STL generation for tube racks and gel electrophoresis combs

The broader product roadmap still includes multi-well molds and basic microfluidic channel molds, but those templates are not registered for artifact generation until the geometry and validation rules are defined.

## Example prompts

```text
Design a rack for 1.5 mL tubes that fits in a standard ice bucket
Create a 4 x 6 tube rack with 11 mm diameter and 15 mm spacing
Make a gel electrophoresis comb with 10 wells
```

## Verification

```bash
npm run backend:test
npm run frontend:lint
npm run frontend:build
```

## Product vision

LabSmith adds a missing tool-creation step to the scientific workflow:

```text
Hypothesis -> Experiment Design -> Tool Creation -> Execution -> Analysis
```

The long-term goal is to let labs produce simple, validated, fabrication-ready hardware on demand instead of relying on expensive niche suppliers or manual CAD work.
