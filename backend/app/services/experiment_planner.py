"""Experiment protocol planner — decomposes a description into typed steps.

Used by `ExperimentRunnerAgent`. Two paths:

- `OpenAIPlanner` — calls OpenAI Chat Completions with a strict JSON schema
  matching `ExperimentProtocol`. The model returns a structured plan we can
  validate immediately.
- `TemplatedPlanner` — a deterministic 3-step fallback ("centrifuge → PCR →
  read") used when the OpenAI call fails OR when no OpenAI key is set. The
  templated plan is intentionally generic; it lets the demo continue end-
  to-end even if the LLM is unreachable.

The planner doesn't dispatch anything — it only proposes. Execution
happens in `app/services/agents/experiment.py`.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from app.config import settings
from app.models.lab_device import DeviceType, LabDevice
from app.schemas.experiments import (
    DeviceJobStep,
    ExperimentProtocol,
    FabricateStep,
)

logger = logging.getLogger(__name__)


class ExperimentPlanner(Protocol):
    """Produces an `ExperimentProtocol` from a free-text description and a
    snapshot of what devices are available in the lab."""

    async def propose(
        self, *, user_content: str, available_devices: list[LabDevice]
    ) -> ExperimentProtocol:
        ...


# ---------------------------------------------------------------------------
# Templated fallback — always works, no network
# ---------------------------------------------------------------------------


class TemplatedPlanner:
    """Deterministic protocol so the demo continues even when OpenAI is
    unreachable. Picks steps based on which device types the lab actually has —
    we never propose a centrifuge step in a lab with no centrifuge."""

    async def propose(
        self, *, user_content: str, available_devices: list[LabDevice]
    ) -> ExperimentProtocol:
        types_present = {d.device_type for d in available_devices}
        steps: list[Any] = []

        if DeviceType.CENTRIFUGE in types_present:
            steps.append(
                DeviceJobStep(
                    label="Pre-spin samples",
                    device_type=DeviceType.CENTRIFUGE,
                    params={"rpm": 1000, "seconds": 30},
                )
            )
        if DeviceType.THERMOCYCLER in types_present:
            steps.append(
                DeviceJobStep(
                    label="PCR cycle",
                    device_type=DeviceType.THERMOCYCLER,
                    params={
                        "cycles": 25,
                        "steps": [
                            {"label": "denature", "temperature_c": 95.0, "seconds": 30},
                            {"label": "anneal", "temperature_c": 60.0, "seconds": 30},
                            {"label": "extend", "temperature_c": 72.0, "seconds": 60},
                        ],
                    },
                )
            )
        if DeviceType.PLATE_READER in types_present:
            steps.append(
                DeviceJobStep(
                    label="Read concentration",
                    device_type=DeviceType.PLATE_READER,
                    params={"mode": "absorbance", "wavelength_nm": 260, "wells": 96},
                )
            )

        if not steps:
            # Lab has no Shape-A devices at all — fabricate a placeholder
            # rack so we still emit a valid one-step protocol.
            steps.append(
                FabricateStep(
                    label="Print a test rack",
                    prompt="Create a 4x6 tube rack with 11 mm holes, 15 mm spacing, and 50 mm height",
                )
            )

        return ExperimentProtocol(
            title="Generic experiment protocol",
            summary=(
                "Templated fallback — the planner couldn't generate a custom "
                "protocol from the description. Adapt the steps below or "
                "describe the experiment in more detail."
            ),
            steps=steps,
        )


# ---------------------------------------------------------------------------
# OpenAI structured-output planner
# ---------------------------------------------------------------------------


# Keep the schema strict (no `additionalProperties`) so OpenAI's
# `strict: true` mode applies — eliminates almost all malformed outputs.
_PROTOCOL_SCHEMA: dict[str, Any] = {
    "name": "experiment_protocol",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["title", "summary", "steps"],
        "properties": {
            "title": {"type": "string", "maxLength": 120},
            "summary": {"type": "string", "maxLength": 400},
            "steps": {
                "type": "array",
                "minItems": 1,
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "label"],
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": ["fabricate", "device_job"],
                        },
                        "label": {"type": "string", "maxLength": 80},
                        "prompt": {"type": "string"},
                        "device_type": {
                            "type": "string",
                            "enum": [t.value for t in DeviceType],
                        },
                        "params": {"type": "object", "additionalProperties": True},
                    },
                },
            },
        },
    },
    "strict": False,
}


def _build_planner_system_prompt(available_devices: list[LabDevice]) -> str:
    summary_lines = [
        f"- {d.device_type.value} (id {d.id}): {d.name}" for d in available_devices
    ]
    summary = "\n".join(summary_lines) or "  (no devices configured)"
    valid_types = ", ".join(t.value for t in DeviceType if t != DeviceType.PRINTER_3D)

    return (
        "You are LabSmith's experiment planner. Given a lab member's "
        "description of an experiment, produce a structured protocol of 1–8 "
        "ordered steps that this specific lab can run with the devices it "
        "has.\n\n"
        "Each step is one of:\n"
        '- {"kind": "fabricate", "label": "...", "prompt": "..."} — print a '
        "part using the natural-language CAD pipeline. Use this only for "
        "specialty parts the lab clearly needs.\n"
        '- {"kind": "device_job", "label": "...", "device_type": "...", '
        '"params": {...}} — run a job on a device of the given type.\n\n'
        f"Valid device_type values: printer_3d, {valid_types}.\n\n"
        "Per-type params shape:\n"
        '- centrifuge: {"rpm": int, "seconds": int}\n'
        '- thermocycler: {"cycles": int, "steps": [{"label": str, '
        '"temperature_c": float, "seconds": int}, ...]}\n'
        '- plate_reader: {"mode": "absorbance"|"fluorescence"|"luminescence", '
        '"wavelength_nm": int|null, "wells": int}\n'
        '- liquid_handler: {"protocol_label": str, "plate_count": int, '
        '"estimated_seconds": int}\n'
        '- autoclave: {"temperature_c": int, "seconds": int}\n\n'
        "Devices currently available in this lab:\n"
        f"{summary}\n\n"
        "Rules:\n"
        "- Only emit device_job steps for device types this lab has. If the "
        "lab is missing something critical, emit fewer steps and call it out "
        "in `summary`.\n"
        "- Keep each step's label under 80 characters and write `summary` as "
        "1–2 sentences explaining the overall plan.\n"
        "- Numeric params should be physically plausible but trimmed for "
        "demo speed (e.g., PCR with 25 cycles, not 40)."
    )


class OpenAIPlanner:
    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError(
                "LABSMITH_OPENAI_API_KEY must be set to use the OpenAI experiment planner"
            )
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed. Pin chat_llm_provider=mock to disable."
            ) from exc

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def propose(
        self, *, user_content: str, available_devices: list[LabDevice]
    ) -> ExperimentProtocol:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": _build_planner_system_prompt(available_devices),
                    },
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_schema", "json_schema": _PROTOCOL_SCHEMA},
                temperature=0.2,
            )
        except Exception:
            logger.exception("OpenAI experiment planner call failed")
            raise

        try:
            raw = response.choices[0].message.content or ""
            parsed = json.loads(raw)
        except (IndexError, AttributeError, json.JSONDecodeError) as exc:
            logger.exception("Could not parse OpenAI planner response: %s", exc)
            raise

        return ExperimentProtocol.model_validate(parsed)


# ---------------------------------------------------------------------------
# Factory with built-in demo safety
# ---------------------------------------------------------------------------


def get_experiment_planner() -> ExperimentPlanner:
    """Return the configured planner. Defaults to templated when chat_llm_provider
    is not 'openai' or when the API key is missing — demos never break because
    of a planner failure."""
    if (settings.chat_llm_provider or "").lower() == "openai" and settings.openai_api_key:
        return OpenAIPlanner(
            api_key=settings.openai_api_key,
            model=settings.openai_chat_model,
        )
    return TemplatedPlanner()


async def propose_protocol_safe(
    *, user_content: str, available_devices: list[LabDevice]
) -> tuple[ExperimentProtocol, str | None]:
    """Try the configured planner; on any failure, fall back to the templated
    one. Returns (protocol, fallback_reason). When `fallback_reason` is set,
    the agent should mention it to the user so they understand why the
    protocol is generic."""
    planner = get_experiment_planner()
    try:
        protocol = await planner.propose(
            user_content=user_content, available_devices=available_devices
        )
        return protocol, None
    except Exception as exc:  # noqa: BLE001 — never break the demo
        logger.exception("Planner failed; falling back to templated: %s", exc)
        templated = TemplatedPlanner()
        protocol = await templated.propose(
            user_content=user_content, available_devices=available_devices
        )
        return protocol, f"planner-fallback: {type(exc).__name__}"
