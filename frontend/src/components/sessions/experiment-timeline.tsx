"use client";

import {
  Beaker,
  Check,
  CircleAlert,
  CircleDashed,
  FlaskConical,
  Loader2,
  Microscope,
  Printer,
  RotateCw,
  Sparkles,
  Thermometer,
} from "lucide-react";
import type { ComponentType } from "react";

import { DeviceResultCard } from "@/components/sessions/device-result-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  DeviceJobStep,
  DeviceType,
  ExperimentStep,
  FabricateStep,
  StepRunState,
  StepStatus,
} from "@/lib/api";
import type { ExperimentState } from "@/lib/use-chat";

interface ExperimentTimelineProps {
  experiment: ExperimentState;
  /** Reserved for future use — kept on the prop signature so callers don't
   *  break. The current implementation reads each step's result from the
   *  step state itself. */
  labId?: string;
}

const TYPE_ICON: Record<DeviceType, ComponentType<{ className?: string }>> = {
  printer_3d: Printer,
  liquid_handler: Beaker,
  centrifuge: RotateCw,
  thermocycler: Thermometer,
  plate_reader: Microscope,
  autoclave: FlaskConical,
};

const TYPE_LABEL: Record<DeviceType, string> = {
  printer_3d: "3D printer",
  liquid_handler: "Liquid handler",
  centrifuge: "Centrifuge",
  thermocycler: "Thermocycler",
  plate_reader: "Plate reader",
  autoclave: "Autoclave",
};

const STATUS_LABEL: Record<StepStatus, string> = {
  pending: "Waiting",
  running: "Running",
  complete: "Done",
  failed: "Failed",
  skipped: "Skipped",
};

/**
 * Vertical timeline for an experiment session. Each step is a card with
 * status icon, label, kind-specific detail, and an animated state for the
 * currently-running one.
 *
 * Auto-hides when the session has no protocol yet — the first user turn
 * triggers the planner, after which `experiment.protocol` is populated and
 * this whole panel appears.
 */
export function ExperimentTimeline({ experiment }: ExperimentTimelineProps) {
  if (!experiment.protocol) return null;

  const completed = experiment.stepStates.filter(
    (s) => s.status === "complete",
  ).length;
  const failed = experiment.stepStates.some((s) => s.status === "failed");

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Sparkles className="h-4 w-4" />
            {experiment.protocol.title}
          </CardTitle>
          <ExperimentBadge state={experiment} />
        </div>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          {experiment.protocol.summary}
        </p>
        {experiment.fallbackReason && (
          <p className="mt-2 rounded-md border border-yellow-200 bg-yellow-50 px-2.5 py-1.5 text-[11px] leading-relaxed text-yellow-800">
            Templated fallback in use ({experiment.fallbackReason}). The plan
            below is generic — describe the experiment in more detail to get
            a tailored protocol.
          </p>
        )}
      </CardHeader>
      <CardContent>
        <ol className="relative space-y-3 pl-4 before:absolute before:left-[7px] before:top-1 before:h-[calc(100%-8px)] before:w-px before:bg-slate-200">
          {experiment.protocol.steps.map((step, index) => {
            const state = experiment.stepStates[index] ?? defaultState();
            return (
              <li key={index} className="relative">
                <span className="absolute -left-[18px] top-1.5">
                  <StepDot status={state.status} />
                </span>
                <StepCard step={step} index={index} state={state} />
              </li>
            );
          })}
        </ol>
        <p className="mt-4 text-xs text-muted-foreground">
          {failed
            ? "Stopped at a failed step."
            : `${completed} of ${experiment.protocol.steps.length} steps complete.`}
        </p>
      </CardContent>
    </Card>
  );
}

function ExperimentBadge({ state }: { state: ExperimentState }) {
  if (state.status === "complete") {
    return (
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-700">
        <Check className="h-3 w-3" /> Complete
      </span>
    );
  }
  if (state.status === "failed") {
    return (
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-red-700">
        <CircleAlert className="h-3 w-3" /> Failed
      </span>
    );
  }
  if (state.status === "running") {
    return (
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-blue-700">
        <Loader2 className="h-3 w-3 animate-spin" /> Running
      </span>
    );
  }
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
      Proposed
    </span>
  );
}

function StepDot({ status }: { status: StepStatus }) {
  if (status === "complete") {
    return (
      <span className="grid h-4 w-4 place-items-center rounded-full bg-emerald-500 text-white">
        <Check className="h-2.5 w-2.5" />
      </span>
    );
  }
  if (status === "running") {
    return (
      <span className="grid h-4 w-4 place-items-center rounded-full bg-blue-500 text-white">
        <Loader2 className="h-2.5 w-2.5 animate-spin" />
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="grid h-4 w-4 place-items-center rounded-full bg-red-500 text-white">
        <CircleAlert className="h-2.5 w-2.5" />
      </span>
    );
  }
  if (status === "skipped") {
    return (
      <span className="grid h-4 w-4 place-items-center rounded-full border border-slate-300 bg-white text-slate-400">
        <CircleDashed className="h-2.5 w-2.5" />
      </span>
    );
  }
  return (
    <span className="grid h-4 w-4 place-items-center rounded-full border border-slate-300 bg-white text-slate-400">
      <CircleDashed className="h-2.5 w-2.5" />
    </span>
  );
}

function StepCard({
  step,
  index,
  state,
}: {
  step: ExperimentStep;
  index: number;
  state: StepRunState;
}) {
  const isActive = state.status === "running";
  return (
    <div
      className={[
        "rounded-md border p-3 transition-all",
        isActive ? "border-blue-200 bg-blue-50/60" : "border-slate-200 bg-background",
        state.status === "failed" ? "border-red-200 bg-red-50/40" : "",
        state.status === "skipped" ? "opacity-60" : "",
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            <span>Step {index + 1}</span>
            <span className="text-slate-300">·</span>
            <span>{step.kind === "fabricate" ? "Fabricate" : TYPE_LABEL[(step as DeviceJobStep).device_type]}</span>
            <span className="text-slate-300">·</span>
            <span>{STATUS_LABEL[state.status]}</span>
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-900">{step.label}</p>
          {step.kind === "fabricate" && (
            <p className="mt-1 text-xs italic text-muted-foreground">
              &ldquo;{(step as FabricateStep).prompt}&rdquo;
            </p>
          )}
          {step.kind === "device_job" && (
            <DeviceJobSummary step={step as DeviceJobStep} />
          )}
          {state.error && (
            <p className="mt-1.5 rounded border border-red-200 bg-red-50 px-2 py-1 text-[11px] text-red-800">
              {state.error}
            </p>
          )}
        </div>
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-slate-900 text-white">
          {iconForStep(step)}
        </span>
      </div>

      {state.result && state.status === "complete" && (
        <div className="mt-3">
          <DeviceResultCard result={state.result} />
        </div>
      )}
    </div>
  );
}

function DeviceJobSummary({ step }: { step: DeviceJobStep }) {
  const params = step.params || {};
  const bits: string[] = [];

  if (step.device_type === "centrifuge") {
    if (params.rpm) bits.push(`${params.rpm} rpm`);
    if (params.seconds) bits.push(`${params.seconds}s`);
  } else if (step.device_type === "thermocycler") {
    if (typeof params.cycles === "number") bits.push(`${params.cycles} cycles`);
    const stepsArr = Array.isArray(params.steps) ? params.steps : [];
    if (stepsArr.length) {
      bits.push(
        stepsArr
          .map((s: Record<string, unknown>) => `${s.temperature_c}°C×${s.seconds}s`)
          .join(" → "),
      );
    }
  } else if (step.device_type === "plate_reader") {
    if (params.mode) bits.push(String(params.mode));
    if (params.wavelength_nm) bits.push(`${params.wavelength_nm} nm`);
    if (params.wells) bits.push(`${params.wells} wells`);
  } else if (step.device_type === "liquid_handler") {
    if (params.protocol_label) bits.push(String(params.protocol_label));
    if (params.plate_count) bits.push(`${params.plate_count} plate${params.plate_count === 1 ? "" : "s"}`);
  } else if (step.device_type === "autoclave") {
    if (params.temperature_c) bits.push(`${params.temperature_c}°C`);
    if (params.seconds) bits.push(`${params.seconds}s`);
  }

  if (bits.length === 0) return null;
  return <p className="mt-1 font-mono text-[11px] text-muted-foreground">{bits.join(" · ")}</p>;
}

function iconForStep(step: ExperimentStep) {
  if (step.kind === "fabricate") {
    return <Printer className="h-4 w-4" />;
  }
  const Icon = TYPE_ICON[(step as DeviceJobStep).device_type] ?? CircleAlert;
  return <Icon className="h-4 w-4" />;
}

function defaultState(): StepRunState {
  return {
    status: "pending",
    dispatched_id: null,
    error: null,
    started_at: null,
    completed_at: null,
  };
}
