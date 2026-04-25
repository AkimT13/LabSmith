# LabForge AI

## 🧠 Overview

LabForge AI is an autonomous design agent that converts natural language descriptions of laboratory needs into fabrication-ready CAD models. It enables researchers to rapidly create low-cost lab hardware such as molds, racks, and fixtures without requiring CAD expertise or expensive commercial suppliers.

The system bridges a critical gap in the scientific workflow: translating experimental intent into physical tools.

---

## 🚀 Motivation

Laboratories frequently rely on simple but expensive components (e.g., tissue microarray molds, tube racks, gel combs) that are overpriced due to:

* Low-volume niche demand
* Lack of automation in design workflows
* Convenience and validation markups

At the same time, many of these parts are geometrically simple and can be fabricated using accessible tools like 3D printers or silicone casting.

LabForge AI automates the design step, reducing cost, time, and friction in experimental workflows.

---

## 🔁 Where This Fits in the Scientific Loop

Traditional loop:

> Hypothesis → Experiment Design → Execution → Analysis

LabForge introduces a missing step:

> Hypothesis → Experiment Design → **Tool Creation** → Execution → Analysis

---

## ✨ Features

* 🗣️ Natural language → CAD generation
* 📐 Parametric design using CadQuery
* 🧩 Template-based part generation (reliable + extensible)
* 📦 Export to STL/STEP for fabrication
* ⚠️ Basic manufacturability validation
* 🔁 Iterative refinement loop (adjust designs based on feedback)

---

## 🧪 Example Inputs

* "Create a tissue microarray mold with 96 wells, 1 mm diameter, 2 mm spacing"
* "Design a rack for 1.5 mL tubes that fits in a standard ice bucket"
* "Make a gel electrophoresis comb with 10 wells"

---

## ⚙️ How It Works

### 1. Natural Language Parsing

The system extracts structured parameters from user input:

```json
{
  "part": "tma_mold",
  "rows": 8,
  "cols": 12,
  "diameter": 1.0,
  "spacing": 2.0,
  "depth": 3.0
}
```

### 2. Template Mapping

The parsed parameters are mapped to predefined parametric CAD templates.

### 3. CAD Generation

CadQuery generates a 3D model based on parameters.

### 4. Validation

Basic checks ensure manufacturability:

* Minimum wall thickness
* Spacing constraints
* Printability heuristics

### 5. Export

Outputs fabrication-ready files:

* `.stl` (3D printing)
* `.step` (CAD/CNC workflows)

---

## 🛠️ Tech Stack

* **Language**: Python
* **CAD Engine**: CadQuery (OpenCascade backend)
* **AI Layer**: LLM (for parsing + agent logic)
* **Frontend**: Simple chat interface (web or CLI)

---

## 🧩 Architecture

```
User Input
   ↓
LLM Parser → Structured Parameters (JSON)
   ↓
Template Selector
   ↓
CadQuery Generator
   ↓
Validation Layer
   ↓
STL / STEP Output
```

---

## 🔬 Supported Part Types (Initial)

* Tissue microarray molds
* Tube racks (microcentrifuge, PCR)
* Gel electrophoresis combs
* Multi-well molds
* Basic microfluidic channel molds

---

## ⚠️ Limitations

* Not intended for clinical or regulated use
* Limited to simple parametric geometries
* No advanced physics simulation (fit, flow, stress)

---

## 🌱 Future Work

* Automated tolerance optimization
* Simulation-assisted design
* Integration with lab robots (e.g., Opentrons)
* Open-source library of lab part templates
* Feedback-driven autonomous design loops

---

## 🧭 Vision

Enable laboratories to design and fabricate their own tools on demand, reducing reliance on expensive suppliers and accelerating scientific progress.

---

## 📦 Getting Started (Conceptual)

```bash
pip install cadquery
python main.py
```

---

## 🤝 Contributing

Contributions are welcome! Especially:

* New parametric templates
* Validation rules
* UI improvements

---

## 📄 License

MIT (or TBD)

---

## 🧠 Tagline

> From hypothesis to hardware — instantly.
