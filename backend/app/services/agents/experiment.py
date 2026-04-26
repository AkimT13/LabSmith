"""Agent for `experiment` sessions (M11 + lab-scoped backgrounding).

End-to-end flow per turn:

1. Quick acknowledgement text streams to the user ("On it — drafting a protocol…").
2. Planner proposes a typed `ExperimentProtocol` from the user's description
   (OpenAI structured output, with a deterministic templated fallback that
   never fails — demo safety).
3. Pre-flight: confirm every `device_type` referenced in the protocol exists
   in this lab. Missing types are reported and their steps skipped, but the
   rest of the experiment still runs.
4. Run state is persisted on `session.current_spec`.
5. **Execution detaches into a background asyncio task** so navigating away
   from the session page does NOT cancel the experiment — the SSE response
   ends but the task keeps writing step state to the DB. The frontend
   bootstraps from `session.current_spec` and polls for updates while the
   experiment is running, exactly like the lab device queue does.
6. On any unhandled error, the background task persists `status="failed"`
   so the UI never shows an experiment "stuck running" forever.

Event catalog (over the *initial* SSE only — the rest is polled):
    text_delta            (1, brief intro line)
    protocol_proposed     (1, full protocol + initial run state)
    message_complete      (1, intro text only — full reply lands later)

Background task — emits no events, only persists state. The frontend reads
state by re-fetching the session.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.artifact import Artifact
from app.models.design_session import DesignSession, SessionType
from app.models.lab_device import DeviceJob, DeviceType, LabDevice
from app.models.message import Message, MessageRole
from app.models.project import Project
from app.models.user import User
from app.schemas.experiments import (
    DeviceJobStep,
    ExperimentProtocol,
    ExperimentRunState,
    FabricateStep,
    StepRunState,
)
from app.services.agents.base import AgentEvent
from app.services.cad_generation import generate_cad_artifacts
from app.services.device_results import generate_result
from app.services.devices import submit_device_job, submit_print_job, tick_lab_devices
from app.services.experiment_planner import propose_protocol_safe
from app.services.spec_extraction import get_spec_extractor
from app.services.storage import artifact_storage_key, get_storage

logger = logging.getLogger(__name__)


# Hard ceiling on a single per-step sleep so a misconfigured device can't
# stall the background task past the demo window. The device job's own
# duration is unaffected — this only caps how long the background task
# waits before marking the step complete.
_STEP_SLEEP_CAP_SECONDS = 180.0

# Module-level registry of running experiments — prevents double-dispatch
# if the user fires another chat turn while one is mid-flight. Keyed by
# session_id; the value is the asyncio Task itself.
_running_experiments: dict[uuid.UUID, asyncio.Task] = {}


class ExperimentRunnerAgent:
    """Proposes and executes multi-step lab protocols across the LDP."""

    session_type = SessionType.EXPERIMENT

    async def run_turn(
        self,
        *,
        db: AsyncSession,
        session: DesignSession,
        user: User,
        user_content: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        loaded = await db.get(DesignSession, session.id)
        if loaded is not None:
            session = loaded

        assistant_message_id = uuid.uuid4()
        assistant_msg = Message(
            id=assistant_message_id,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content="",
            metadata_=None,
        )
        db.add(assistant_msg)
        await db.flush()

        # Reject mid-run double-starts — much friendlier than two background
        # tasks racing for the same session row.
        if session.id in _running_experiments and not _running_experiments[
            session.id
        ].done():
            text = (
                "An experiment is already running in this session. Watch the "
                "timeline — it'll keep updating even if you navigate away."
            )
            assistant_msg.content = text
            yield {
                "event": "text_delta",
                "data": {"message_id": str(assistant_message_id), "delta": text},
            }
            yield {
                "event": "message_complete",
                "data": {"message_id": str(assistant_message_id), "content": text},
            }
            await db.commit()
            return

        intro = "On it — drafting a protocol from your description."
        assistant_msg.content = intro
        yield {
            "event": "text_delta",
            "data": {"message_id": str(assistant_message_id), "delta": intro},
        }

        # 1. Plan the protocol (with templated fallback for demo safety).
        lab_id = await _lab_id_for_session(db, session=session)
        if lab_id is None:
            yield _failure_event("missing_lab", "This session isn't bound to a lab.")
            yield _message_complete(assistant_message_id, intro)
            await db.commit()
            return

        available_devices = await _available_devices_for_lab(db, lab_id=lab_id)
        protocol, fallback_reason = await propose_protocol_safe(
            user_content=user_content, available_devices=available_devices
        )

        # 2. Pre-flight: filter out steps that can't run in this lab.
        present_types = {d.device_type for d in available_devices}
        executable_steps, skipped_steps = _split_executable(protocol.steps, present_types)

        run_state = ExperimentRunState(
            protocol=protocol,
            step_states=[
                StepRunState(status="skipped" if step in skipped_steps else "pending")
                for step in protocol.steps
            ],
            status="running",
        )
        session.current_spec = run_state.model_dump(mode="json")
        session.part_type = None
        await db.commit()

        proposed_payload = {
            "protocol": protocol.model_dump(mode="json"),
            "step_states": [s.model_dump(mode="json") for s in run_state.step_states],
            "fallback_reason": fallback_reason,
            "skipped_step_indices": [
                i for i, step in enumerate(protocol.steps) if step in skipped_steps
            ],
        }
        yield {"event": "protocol_proposed", "data": proposed_payload}

        # 3. Spawn the background task. SSE closes after `message_complete`
        # below; the task keeps running and persists state to session.current_spec
        # after each step. Frontend polls `GET /sessions/{id}` to follow along.
        task = asyncio.create_task(
            _execute_experiment_background(
                session_id=session.id,
                user_id=user.id,
                lab_id=lab_id,
                assistant_message_id=assistant_message_id,
                intro_text=intro,
                protocol=protocol,
                skipped_step_keys={
                    id(step) for step in skipped_steps  # noqa: any-anymatch
                },
                fallback_reason=fallback_reason,
            )
        )
        _running_experiments[session.id] = task

        def _cleanup(_: asyncio.Task) -> None:
            _running_experiments.pop(session.id, None)

        task.add_done_callback(_cleanup)

        # 4. Close the SSE — execution continues in the background.
        yield _message_complete(assistant_message_id, intro)


# ---------------------------------------------------------------------------
# Background execution
# ---------------------------------------------------------------------------


async def _execute_experiment_background(
    *,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    lab_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    intro_text: str,
    protocol: ExperimentProtocol,
    skipped_step_keys: set[int],
    fallback_reason: str | None,
) -> None:
    """Runs entirely outside the request lifecycle. Uses a fresh DB session
    so it survives request cleanup. Catches all exceptions — never bubbles."""
    try:
        async with async_session_factory() as db:
            session = await db.get(DesignSession, session_id)
            user = await db.get(User, user_id)
            assistant_msg = await db.get(Message, assistant_message_id)
            if session is None or user is None or assistant_msg is None:
                logger.warning(
                    "Background experiment %s aborted — session/user/message missing",
                    session_id,
                )
                return

            run_state = ExperimentRunState.model_validate(session.current_spec or {})
            executable_count = 0
            terminal_failure: str | None = None

            for index, step in enumerate(protocol.steps):
                if id(step) in skipped_step_keys:
                    continue
                executable_count += 1

                run_state.step_states[index].status = "running"
                run_state.step_states[index].started_at = _now_iso()
                session.current_spec = run_state.model_dump(mode="json")
                await db.commit()

                try:
                    dispatched_id, sleep_seconds = await _execute_step(
                        db, lab_id=lab_id, user=user, session=session, step=step
                    )
                except Exception as exc:  # noqa: BLE001 — surface as state, never crash
                    logger.exception("Experiment step %d failed: %s", index, exc)
                    detail = getattr(exc, "detail", None) or str(exc)
                    run_state.step_states[index].status = "failed"
                    run_state.step_states[index].error = detail
                    run_state.step_states[index].completed_at = _now_iso()
                    session.current_spec = run_state.model_dump(mode="json")
                    await db.commit()
                    terminal_failure = detail
                    break

                run_state.step_states[index].dispatched_id = dispatched_id
                await db.commit()

                await asyncio.sleep(min(_STEP_SLEEP_CAP_SECONDS, max(0.5, sleep_seconds)))

                # For device_job steps, tick the lab so the underlying job
                # promotes to COMPLETE (which generates the result via
                # `device_results.generate_result`) and copy that result
                # onto the step state. Embedding it here means the timeline
                # UI doesn't need to cross-reference the live device
                # snapshot — completed jobs aren't there.
                if step.kind == "device_job" and dispatched_id is not None:
                    try:
                        await tick_lab_devices(db, lab_id=lab_id)
                        result = await _fetch_job_result(
                            db,
                            job_id=dispatched_id,
                            device_type=step.device_type,
                            payload=step.params or {},
                        )
                        if result:
                            run_state.step_states[index].result = result
                    except Exception:  # noqa: BLE001 — never block step completion
                        logger.exception(
                            "Couldn't fetch result for job %s", dispatched_id
                        )

                run_state.step_states[index].status = "complete"
                run_state.step_states[index].completed_at = _now_iso()
                session.current_spec = run_state.model_dump(mode="json")
                await db.commit()

            if terminal_failure is not None:
                run_state.status = "failed"
                tail = (
                    f" The experiment stopped at a failed step: {terminal_failure}"
                )
            else:
                run_state.status = "complete"
                skipped_count = sum(
                    1 for i, step in enumerate(protocol.steps)
                    if id(step) in skipped_step_keys
                )
                if skipped_count:
                    missing = sorted(
                        {
                            (step.device_type.value if hasattr(step, "device_type") else "?")
                            for step in protocol.steps
                            if id(step) in skipped_step_keys
                        }
                    )
                    tail = (
                        f" Ran {executable_count} of {len(protocol.steps)} steps. "
                        f"Skipped steps that needed device types you don't have yet: "
                        f"{', '.join(missing)}."
                    )
                else:
                    tail = (
                        f" Done — ran all {executable_count} steps of "
                        f'"{protocol.title}".'
                    )

            if fallback_reason:
                tail = (
                    " (Used a templated protocol because the planner couldn't "
                    f"generate one: {fallback_reason}.)" + tail
                )

            session.current_spec = run_state.model_dump(mode="json")
            assistant_msg.content = f"{intro_text}{tail}"
            await db.commit()
    except Exception as exc:  # noqa: BLE001 — last-ditch
        logger.exception("Background experiment %s crashed: %s", session_id, exc)
        # Best-effort: mark as failed in a separate session so the UI doesn't
        # hang forever on status=running.
        try:
            async with async_session_factory() as db:
                session = await db.get(DesignSession, session_id)
                if session is not None and session.current_spec:
                    spec = dict(session.current_spec)
                    spec["status"] = "failed"
                    session.current_spec = spec
                    await db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to mark experiment %s as failed", session_id)


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------


async def _execute_step(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
    session: DesignSession,
    step: FabricateStep | DeviceJobStep,
) -> tuple[uuid.UUID | None, float]:
    """Execute a single step and return (dispatched_id, seconds_to_wait)."""
    if step.kind == "device_job":
        return await _execute_device_step(db, lab_id=lab_id, user=user, step=step)
    if step.kind == "fabricate":
        return await _execute_fabricate_step(
            db, lab_id=lab_id, user=user, session=session, step=step
        )
    raise ValueError(f"Unknown step kind: {step.kind}")


async def _execute_device_step(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
    step: DeviceJobStep,
) -> tuple[uuid.UUID, float]:
    job = await submit_device_job(
        db,
        lab_id=lab_id,
        user=user,
        device_type=step.device_type,
        payload=step.params or {},
        label=step.label,
    )
    return job.id, job.simulated_duration_seconds


async def _execute_fabricate_step(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
    session: DesignSession,
    step: FabricateStep,
) -> tuple[uuid.UUID, float]:
    extractor = get_spec_extractor()
    extraction = await extractor.extract(
        user_content=step.prompt,
        current_spec=None,
        message_history=[],
    )
    if extraction.part_request is None:
        raise RuntimeError(
            extraction.error
            or "Couldn't extract a part spec from the fabricate step's prompt."
        )
    part_request = extraction.part_request

    from labsmith.validation import build_printability_report, validate_part_request

    issues = [
        {
            "severity": issue.severity.value,
            "code": issue.code,
            "message": issue.message,
            "field": issue.field,
        }
        for issue in validate_part_request(part_request)
    ]
    if any(i["severity"] == "error" for i in issues):
        raise RuntimeError(
            "Fabricate step has validation errors: "
            + "; ".join(i["message"] for i in issues if i["severity"] == "error")
        )

    printability = build_printability_report(part_request)

    next_version_row = await db.execute(
        select(Artifact.version)
        .where(Artifact.session_id == session.id)
        .order_by(desc(Artifact.version))
        .limit(1)
    )
    next_version = (next_version_row.scalar_one_or_none() or 0) + 1

    generated = (await generate_cad_artifacts(part_request))[0]

    artifact = Artifact(
        session_id=session.id,
        message_id=None,
        artifact_type=generated.artifact_type,
        file_path=None,
        file_size_bytes=None,
        spec_snapshot=part_request.model_dump(mode="json"),
        validation={"issues": issues, "printability": printability},
        version=next_version,
    )
    db.add(artifact)
    await db.flush()
    await db.refresh(artifact)

    storage = get_storage()
    key = artifact_storage_key(
        session_id=str(session.id),
        artifact_id=str(artifact.id),
        version=next_version,
        extension=generated.extension,
    )
    stored = await storage.save(key, generated.data, content_type=generated.content_type)
    artifact.file_path = stored.key
    artifact.file_size_bytes = stored.size_bytes
    await db.flush()
    await db.refresh(artifact)

    try:
        print_jobs = await submit_print_job(
            db,
            lab_id=lab_id,
            user=user,
            artifact_id=artifact.id,
            copies=1,
        )
    except Exception as exc:  # noqa: BLE001 — printer unavailable is recoverable
        logger.info(
            "Fabricate step generated artifact %s but couldn't dispatch a "
            "print (lab may have no printer): %s",
            artifact.id,
            exc,
        )
        return artifact.id, 2.0

    if not print_jobs:
        return artifact.id, 1.0
    return artifact.id, print_jobs[0].simulated_duration_seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_executable(
    steps: list[Any], present_types: set[DeviceType]
) -> tuple[list[Any], list[Any]]:
    """Returns (executable, skipped). Identity is by object reference so we
    can match steps in the background task without re-validating shapes."""
    executable: list[Any] = []
    skipped: list[Any] = []
    for step in steps:
        if (
            isinstance(step, DeviceJobStep)
            and step.device_type != DeviceType.PRINTER_3D
            and step.device_type not in present_types
        ):
            skipped.append(step)
        else:
            executable.append(step)
    return executable, skipped


async def _available_devices_for_lab(
    db: AsyncSession, *, lab_id: uuid.UUID
) -> list[LabDevice]:
    result = await db.execute(
        select(LabDevice)
        .where(LabDevice.laboratory_id == lab_id)
        .order_by(LabDevice.created_at)
    )
    return list(result.scalars().all())


async def _lab_id_for_session(
    db: AsyncSession, *, session: DesignSession
) -> uuid.UUID | None:
    result = await db.execute(
        select(Project.laboratory_id).where(Project.id == session.project_id)
    )
    return result.scalar_one_or_none()


async def _fetch_job_result(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    device_type: DeviceType,
    payload: dict,
) -> dict | None:
    """Pull the simulated result off a device job. If the tick hasn't yet
    promoted the job to COMPLETE, generate the result inline using the same
    deterministic generator so the timeline still shows something."""
    row = await db.execute(select(DeviceJob).where(DeviceJob.id == job_id))
    job = row.scalar_one_or_none()
    if job is None:
        return None
    if job.result:
        return dict(job.result)

    # Race: step's sleep finished before the device tick promoted the job.
    # Generate the result inline using the same generator (deterministic
    # per job_id, so we don't conflict with whatever tick will write later).
    result = generate_result(
        device_type=device_type, job_id=job.id, payload=payload
    )
    job.result = result
    await db.flush()
    return result


def _failure_event(reason: str, detail: str) -> AgentEvent:
    return {
        "event": "experiment_failed",
        "data": {"reason": reason, "detail": detail},
    }


def _message_complete(message_id: uuid.UUID, content: str) -> AgentEvent:
    return {
        "event": "message_complete",
        "data": {"message_id": str(message_id), "content": content},
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
