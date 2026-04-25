# LabSmith — Engineering Handoff

## Objective

Build an MVP that converts natural-language requests for simple lab hardware into validated parametric CAD models and exports fabrication-ready files.

The first target is **simple, high-value, parametric lab parts** such as:

* tissue microarray molds
* tube racks
* gel electrophoresis combs
* simple multi-well molds

The product should feel like a lightweight design copilot for labs: a user describes a needed part, the system extracts structured parameters, chooses a template, generates geometry with CadQuery, validates manufacturability, and exports STL/STEP.

---

## Product Scope

### In scope for MVP

* Natural language input
* Structured parameter extraction
* Template-based CAD generation
* Basic validation rules
* STL export
* Simple local CLI or minimal web UI
* Support for 1 to 3 part templates initially

### Out of scope for MVP

* Freeform CAD generation
* Complex organic geometry
* Full physics simulation
* Clinical or regulated workflows
* Printer-specific slicing and G-code generation
* Multi-agent orchestration beyond simple modular services

---

## Recommended Technical Approach

Use a **controlled pipeline**, not raw LLM-to-code generation.

### Required design principle

Do **not** let the language model generate arbitrary CadQuery code.

Instead:

1. User submits natural language request
2. Parser converts it into a structured JSON spec
3. Template router maps spec to a supported part family
4. Deterministic Python/CadQuery code builds the model
5. Validator checks dimensions and manufacturability heuristics
6. Exporter writes STL and optionally STEP
7. Response returns files plus warnings

This keeps the system reliable, testable, and safe.

---

## Proposed System Architecture

```text
User Input
   ↓
Intent + Parameter Parser
   ↓
Normalized Part Spec (JSON)
   ↓
Template Router
   ↓
CadQuery Generator
   ↓
Validation Layer
   ↓
Exporter
   ↓
Artifacts + Summary + Warnings
```

### Modules

* `parser/` — natural language to structured spec
* `schemas/` — Pydantic models for each part type
* `templates/` — deterministic CadQuery builders
* `validators/` — rule-based checks
* `export/` — STL/STEP generation
* `app/` — CLI or web entrypoint
* `tests/` — unit tests and golden specs

---

## Suggested Repository Structure

```text
labsmith/
├─ README.md
├─ pyproject.toml
├─ requirements.txt
├─ .env.example
├─ app/
│  ├─ cli.py
│  ├─ api.py
│  └─ main.py
├─ parser/
│  ├─ extract.py
│  ├─ normalize.py
│  └─ prompts.py
├─ schemas/
│  ├─ common.py
│  ├─ tma_mold.py
│  ├─ tube_rack.py
│  └─ gel_comb.py
├─ templates/
│  ├─ registry.py
│  ├─ tma_mold.py
│  ├─ tube_rack.py
│  └─ gel_comb.py
├─ validators/
│  ├─ common.py
│  ├─ tma_mold.py
│  ├─ tube_rack.py
│  └─ gel_comb.py
├─ export/
│  ├─ stl.py
│  └─ step.py
├─ examples/
│  ├─ tma_request.json
│  ├─ tube_rack_request.json
│  └─ gel_comb_request.json
├─ output/
├─ tests/
│  ├─ test_parser.py
│  ├─ test_templates.py
│  ├─ test_validators.py
│  └─ fixtures/
└─ docs/
   ├─ architecture.md
   └─ milestones.md
```

---

## Core Data Contract

Define a normalized JSON contract between parser and CAD generator.

### Base request schema

```json
{
  "part_type": "tma_mold",
  "units": "mm",
  "parameters": {},
  "constraints": {
    "fabrication_method": "sla_print",
    "material": "resin"
  },
  "notes": []
}
```

### Example: tissue microarray mold

```json
{
  "part_type": "tma_mold",
  "units": "mm",
  "parameters": {
    "rows": 8,
    "cols": 12,
    "well_diameter": 1.0,
    "well_depth": 3.0,
    "well_spacing": 2.0,
    "margin": 3.0,
    "base_thickness": 5.0,
    "corner_radius": 1.0
  },
  "constraints": {
    "fabrication_method": "sla_print",
    "material": "resin"
  },
  "notes": []
}
```

### Example: tube rack

```json
{
  "part_type": "tube_rack",
  "units": "mm",
  "parameters": {
    "rows": 4,
    "cols": 6,
    "hole_diameter": 8.2,
    "hole_spacing": 12.0,
    "plate_thickness": 4.0,
    "height": 25.0,
    "margin": 6.0
  },
  "constraints": {
    "fabrication_method": "fdm_print",
    "material": "pla"
  },
  "notes": []
}
```

---

## Template Strategy

Each supported part type should have:

1. a Pydantic schema
2. a default parameter set
3. a deterministic CadQuery generator
4. a validator
5. sample requests and expected artifacts

### Initial templates to implement

#### 1. TMA mold

Why first:

* directly tied to the motivating use case
* highly parametric and grid-based
* easy to explain in demos

Suggested geometry:

* rectangular base block
* repeated cylindrical wells or pegs depending on mold convention
* configurable array spacing and margins

#### 2. Tube rack

Why second:

* simple geometry
* broadly useful
* good demonstration of fit/tolerance logic

Suggested geometry:

* rectangular plate with repeated circular cutouts
* optional feet or sidewalls

#### 3. Gel comb

Why third:

* very simple
* good for demonstrating slot arrays instead of holes

Suggested geometry:

* flat comb body
* repeated tooth extrusions
* configurable tooth width, spacing, count, depth

---

## Parser Design

The parser should return **structured JSON only**.

### Recommended approach

Use an LLM or rules-based extractor to produce a typed spec.

#### Parser responsibilities

* identify supported part type
* extract numeric parameters
* fill in defaults for omitted fields
* normalize units
* capture uncertainty or assumptions in `notes`

#### Parser failure behavior

If the request is underspecified, do not fail hard. Instead:

* infer safe defaults
* attach warnings
* continue generation where possible

Example warning:

* `well depth not specified; defaulted to 3.0 mm`

### Example parser output

```json
{
  "part_type": "gel_comb",
  "units": "mm",
  "parameters": {
    "num_teeth": 10,
    "tooth_width": 5.0,
    "tooth_depth": 8.0,
    "tooth_spacing": 2.0,
    "comb_thickness": 3.0,
    "backbone_height": 12.0
  },
  "constraints": {
    "fabrication_method": "fdm_print",
    "material": "pla"
  },
  "notes": [
    "units inferred as millimeters",
    "comb thickness defaulted to 3.0 mm"
  ]
}
```

---

## Validation Layer

Use rule-based validation first. Avoid simulation in milestone 1.

### Validation output contract

```json
{
  "valid": true,
  "warnings": [],
  "errors": []
}
```

### Example validation checks

#### Global checks

* all required fields present after normalization
* dimensions are positive
* total part envelope fits target build volume if specified

#### TMA mold checks

* wall thickness between adjacent wells exceeds minimum threshold
* well depth does not exceed base thickness minus safety margin
* spacing is sufficient for printability

#### Tube rack checks

* hole spacing leaves enough material between adjacent holes
* hole diameter is within expected range for named tube types if used
* height and plate thickness are printable

#### Gel comb checks

* tooth spacing not too small for print method
* teeth are not too thin or too deep for intended print orientation

### Suggested threshold examples

These can be constants initially and refined later.

* minimum printable wall thickness for SLA: `0.5 mm`
* minimum printable wall thickness for FDM: `1.2 mm`
* minimum tooth width for FDM comb: `1.0 mm`
* default tolerance slack for fit features: `0.2 to 0.4 mm`

---

## Export Requirements

### Required outputs for milestone 1

* STL file
* machine-readable JSON spec
* validation report JSON

### Optional outputs

* STEP file
* preview PNG
* metadata manifest

### Suggested artifact layout

```text
output/
└─ request_001/
   ├─ model.stl
   ├─ spec.json
   ├─ validation.json
   └─ summary.txt
```

---

## CLI Behavior for MVP

A CLI is enough for the first milestone.

### Example command

```bash
python -m app.cli "Create a tissue microarray mold with 96 wells, 1 mm diameter, 2 mm spacing"
```

### Expected behavior

* parse input
* print normalized spec
* run validator
* generate model
* export STL
* print output path and warnings

### Example console output

```text
Part type: tma_mold
Status: generated with warnings
Warnings:
- well depth not specified; defaulted to 3.0 mm
Output:
- output/request_001/model.stl
- output/request_001/spec.json
- output/request_001/validation.json
```

---

## Suggested Python Interfaces

### Schema models

```python
class BasePartSpec(BaseModel):
    part_type: str
    units: str = "mm"
    parameters: dict
    constraints: dict = {}
    notes: list[str] = []
```

### Template registry

```python
TEMPLATE_REGISTRY = {
    "tma_mold": build_tma_mold,
    "tube_rack": build_tube_rack,
    "gel_comb": build_gel_comb,
}
```

### Generator interface

```python
def build_part(spec: BasePartSpec):
    builder = TEMPLATE_REGISTRY[spec.part_type]
    return builder(spec)
```

### Validator interface

```python
def validate_spec(spec: BasePartSpec) -> dict:
    ...
```

---

## CadQuery Implementation Notes

### Recommended pattern

Each template file should expose one deterministic builder function.

Example:

```python
def build_tma_mold(spec: TMAMoldSpec):
    # create base block
    # pattern wells
    # subtract or add features
    # return CadQuery solid
```

### Guidance

* keep template builders pure and deterministic
* separate geometry creation from validation
* centralize common arraying helpers and dimension helpers
* export only after passing validation unless explicitly overridden

### Important constraint

Do not generate CadQuery code from user text directly. The only code path to geometry should be the trusted template library.

---

## Testing Plan

### Unit tests

* parser extracts expected part type and defaults
* validators reject impossible dimensions
* template builders return solids without errors
* exporters produce files

### Golden test cases

Maintain a few known-good JSON specs and verify they always build.

Examples:

* `8x12 tma mold`
* `24-hole tube rack`
* `10-tooth gel comb`

### Failure tests

* negative dimensions
* impossible spacing
* unsupported part names
* missing critical parameters that cannot be inferred

---

## UX Guidelines

The system should always tell the user three things clearly:

1. what part it inferred
2. what assumptions it made
3. whether the design is fabrication-safe according to current heuristics

Good UX output structure:

* inferred part type
* extracted parameters
* assumptions/defaults used
* warnings/errors
* generated files

---

## Risks and Mitigations

### Risk: parser misclassifies part type

Mitigation:

* restrict initial vocabulary to supported part families
* use confidence thresholds
* fallback to `unsupported_part` with guidance

### Risk: geometry builds but is not practical

Mitigation:

* add conservative validation thresholds
* surface warnings prominently
* keep milestone 1 limited to simple parts

### Risk: too much hackathon scope

Mitigation:

* implement only one excellent template first
* choose CLI over polished frontend initially
* use deterministic exports, not simulation

---

## Suggested Implementation Direction

The implementation should follow a controlled, template-based architecture rather than freeform CAD generation. Natural language requests should be parsed into structured parameters, routed to a supported part template, validated with simple manufacturability rules, and then converted into fabrication-ready geometry using CadQuery.

The most important technical principle is reliability: the language model should interpret user intent and extract structured values, but deterministic Python code should remain responsible for actual geometry generation. This makes the system easier to test, safer to extend, and much more robust for real use.

As the system grows, new supported lab parts should be added as modular templates with their own schemas, validators, and geometry builders. That allows the project to scale from one or two parts into a broader library of low-cost lab hardware without changing the core architecture.

---

## What Good Looks Like

A strong implementation should make the workflow feel simple and trustworthy. A user should be able to describe a needed lab part in plain language, see the interpreted design parameters, understand any assumptions or warnings, and receive a fabrication-ready output file.

The result should feel less like a chatbot and more like an autonomous scientific design tool: one that reduces friction between identifying an experimental need and creating the physical hardware required to carry it out.

---

## Final Recommendation

Keep the initial implementation narrow, controlled, and highly reliable. The value of the project comes from proving that natural-language scientific intent can be translated into practical, low-cost physical tools through a structured AI-plus-parametric-CAD workflow.

Once that core loop is working well, the project can expand naturally into a reusable platform for open, accessible lab hardware generation.
