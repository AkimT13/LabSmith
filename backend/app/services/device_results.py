"""Simulated post-completion reports for lab devices (Tier-2 demo polish).

Each device type has a `_generate_*` function that returns a dict shaped
for the matching React component. The data is faked but plausible — we use
the job's payload (rpm, cycles, wells, etc.) as a seed so reports look
internally consistent with what was requested.

Determinism: each generator seeds a `random.Random` from the job id, so
the same job ID always yields the same report. Useful for repeatable
demos and for the frontend to cache the heatmap.

Shape contract — every result must have:
- `kind`: matches the device type (used by the renderer to dispatch)
- `headline`: one short sentence summary surfaced on the timeline
- `metrics`: key-value pairs for the small grey card (always renderable)
- ...plus type-specific extras (heatmap data, trace points, etc.)

If a generator raises (shouldn't happen — they're pure data), the caller
swallows the exception and stores a minimal `{kind, headline, metrics}`
fallback so the timeline never breaks.
"""
from __future__ import annotations

import math
import random
import uuid
from typing import Any

from app.models.lab_device import DeviceType


def generate_result(
    *, device_type: DeviceType, job_id: uuid.UUID, payload: dict | None
) -> dict:
    """Dispatch to the per-type generator. Always returns something — never
    raises. A garbage payload yields the type's default report."""
    payload = payload or {}
    rng = random.Random(int(uuid.UUID(str(job_id)).int))

    try:
        if device_type == DeviceType.CENTRIFUGE:
            return _generate_centrifuge(rng, payload)
        if device_type == DeviceType.THERMOCYCLER:
            return _generate_thermocycler(rng, payload)
        if device_type == DeviceType.PLATE_READER:
            return _generate_plate_reader(rng, payload)
        if device_type == DeviceType.LIQUID_HANDLER:
            return _generate_liquid_handler(rng, payload)
        if device_type == DeviceType.AUTOCLAVE:
            return _generate_autoclave(rng, payload)
    except Exception:
        # Generators shouldn't raise, but the demo never breaks because of a
        # bad sim report.
        pass

    return {
        "kind": device_type.value,
        "headline": "Job complete.",
        "metrics": {},
    }


# ---------------------------------------------------------------------------
# Per-type generators
# ---------------------------------------------------------------------------


def _generate_centrifuge(rng: random.Random, payload: dict) -> dict:
    rpm = int(payload.get("rpm", 1000))
    seconds = int(payload.get("seconds", 60))
    # Tighter pellet at higher RCF * time. RCF is rough — sim, not physics.
    rcf = round((rpm / 1000) ** 2 * 100)
    quality_score = min(100, round(0.5 * rcf + seconds / 2 + rng.uniform(-5, 5)))
    quality = (
        "tight"
        if quality_score >= 70
        else "loose"
        if quality_score >= 40
        else "diffuse"
    )
    return {
        "kind": "centrifuge",
        "headline": (
            f"Spun at {rpm} rpm × {seconds}s · pellet quality: {quality}"
        ),
        "metrics": {
            "rpm": rpm,
            "seconds": seconds,
            "rcf_g": rcf,
            "pellet_quality": quality,
            "pellet_score": quality_score,
        },
    }


def _generate_thermocycler(rng: random.Random, payload: dict) -> dict:
    cycles = int(payload.get("cycles", 25))
    steps = payload.get("steps") or []
    if not isinstance(steps, list) or not steps:
        steps = [
            {"label": "denature", "temperature_c": 95.0, "seconds": 30},
            {"label": "anneal", "temperature_c": 60.0, "seconds": 30},
            {"label": "extend", "temperature_c": 72.0, "seconds": 60},
        ]

    # Build a temperature trace. We sample one point per step + a 10s ramp
    # between, abbreviated to ~2 cycles for chart legibility, with a label
    # noting the full cycle count.
    sample_cycles = min(cycles, 3)
    trace: list[dict[str, float]] = []
    t = 0.0
    last_temp = 25.0
    for _ in range(sample_cycles):
        for step in steps:
            target = float(step.get("temperature_c", 60))
            ramp = 8.0
            t += ramp
            trace.append({"t": round(t, 1), "temp": round((last_temp + target) / 2, 1)})
            t += float(step.get("seconds", 30)) / 5.0  # compress for chart
            trace.append({"t": round(t, 1), "temp": target})
            last_temp = target

    # Simulated yield: scales with cycles, decays past ~30, with noise.
    base_yield = max(2.0, min(50.0, cycles * 1.4 - max(0, cycles - 30) * 0.5))
    yield_ng_ul = round(base_yield + rng.uniform(-2, 2), 2)
    a260_a280 = round(rng.uniform(1.78, 1.95), 2)

    return {
        "kind": "thermocycler",
        "headline": (
            f"{cycles} cycles complete · estimated yield {yield_ng_ul} ng/µL"
        ),
        "metrics": {
            "cycles": cycles,
            "yield_ng_ul": yield_ng_ul,
            "a260_a280": a260_a280,
            "displayed_cycles": sample_cycles,
        },
        "trace": trace,
        "program": [
            {
                "label": str(s.get("label", "step")),
                "temperature_c": float(s.get("temperature_c", 60)),
                "seconds": int(s.get("seconds", 30)),
            }
            for s in steps
        ],
    }


def _generate_plate_reader(rng: random.Random, payload: dict) -> dict:
    """The crown-jewel demo visual: a 96-well heatmap with realistic
    absorbance values. Most wells cluster around a low baseline; we sprinkle
    a few "hits" that read 5-10x higher — recognizable to anyone who's
    looked at real plate-reader software."""
    wells = int(payload.get("wells", 96))
    rows = 8 if wells == 96 else 16 if wells == 384 else max(1, int(math.sqrt(wells)))
    cols = wells // rows if rows else wells

    mode = str(payload.get("mode", "absorbance"))
    wavelength = payload.get("wavelength_nm", 260)

    # Baseline: gaussian around 0.10 with a few hits.
    grid: list[list[float]] = []
    flat: list[float] = []
    hits: list[tuple[int, int]] = []
    hit_count = max(2, wells // 24)
    hit_positions = {
        (rng.randint(0, rows - 1), rng.randint(0, cols - 1)) for _ in range(hit_count)
    }

    for r in range(rows):
        row: list[float] = []
        for c in range(cols):
            if (r, c) in hit_positions:
                value = round(rng.uniform(0.55, 1.20), 3)
                hits.append((r, c))
            else:
                value = round(max(0.0, rng.gauss(0.12, 0.04)), 3)
            row.append(value)
            flat.append(value)
        grid.append(row)

    mean = round(sum(flat) / len(flat), 3)
    cv = round((statistics_stdev(flat) / mean) * 100 if mean else 0.0, 1)

    headline_value = "absorbance" if mode == "absorbance" else mode
    headline = (
        f"{wells} wells read · {headline_value}"
        + (f" at {wavelength} nm" if wavelength else "")
        + f" · mean {mean}"
    )
    return {
        "kind": "plate_reader",
        "headline": headline,
        "metrics": {
            "wells": wells,
            "mean": mean,
            "cv_percent": cv,
            "hits": len(hits),
            "mode": mode,
            "wavelength_nm": wavelength,
        },
        "grid": grid,
        "rows": rows,
        "cols": cols,
    }


def _generate_liquid_handler(rng: random.Random, payload: dict) -> dict:
    plate_count = int(payload.get("plate_count", 1))
    protocol_label = str(payload.get("protocol_label", "stamp"))
    wells_per_plate = 96
    total_wells = plate_count * wells_per_plate

    # Simulated dispense map for the FIRST plate — a 8x12 grid where most
    # cells are "dispensed" but with a couple of skipped wells (negative
    # controls / edge effects) to look real.
    rows, cols = 8, 12
    grid: list[list[bool]] = []
    skipped: list[tuple[int, int]] = []
    for r in range(rows):
        row: list[bool] = []
        for c in range(cols):
            dispensed = rng.random() > 0.04  # ~4 wells skipped on average
            if not dispensed:
                skipped.append((r, c))
            row.append(dispensed)
        grid.append(row)

    return {
        "kind": "liquid_handler",
        "headline": (
            f"{plate_count} plate{'s' if plate_count != 1 else ''} stamped · "
            f"{total_wells - len(skipped) * plate_count} wells dispensed · "
            f"protocol: {protocol_label}"
        ),
        "metrics": {
            "plate_count": plate_count,
            "wells_per_plate": wells_per_plate,
            "total_wells": total_wells,
            "skipped_wells": len(skipped) * plate_count,
            "protocol": protocol_label,
        },
        "grid": grid,
        "rows": rows,
        "cols": cols,
    }


def _generate_autoclave(rng: random.Random, payload: dict) -> dict:
    target_c = int(payload.get("temperature_c", 121))
    seconds = int(payload.get("seconds", 1200))
    # Build a temp trace: ramp up → hold at target → cool down, sampled
    # ~30 points for a smooth chart.
    trace: list[dict[str, float]] = []
    samples = 30
    for i in range(samples + 1):
        progress = i / samples
        if progress < 0.25:
            temp = 20 + (target_c - 20) * (progress / 0.25)
        elif progress < 0.85:
            temp = target_c + rng.uniform(-0.4, 0.4)
        else:
            temp = target_c - (target_c - 25) * ((progress - 0.85) / 0.15)
        trace.append({"t": round(progress * seconds, 1), "temp": round(temp, 1)})

    indicator = "passed"
    return {
        "kind": "autoclave",
        "headline": (
            f"Cycle complete · {target_c}°C × {seconds}s · biological indicator: {indicator}"
        ),
        "metrics": {
            "target_c": target_c,
            "seconds": seconds,
            "indicator": indicator,
            "peak_c": max(p["temp"] for p in trace),
        },
        "trace": trace,
    }


# ---------------------------------------------------------------------------
# Tiny stats helper (no numpy import for one stdev call)
# ---------------------------------------------------------------------------


def statistics_stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)
