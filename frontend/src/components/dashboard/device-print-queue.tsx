"use client";

import {
  Beaker,
  CircleAlert,
  FlaskConical,
  Microscope,
  Printer,
  RotateCw,
  Thermometer,
  Trash2,
} from "lucide-react";
import type { ComponentType } from "react";

import { Button } from "@/components/ui/button";
import type { DeviceJob, DeviceStatus, DeviceType, LabDevice } from "@/lib/api";

interface DevicePrintQueueProps {
  device: LabDevice;
  /** When provided, shows a destructive "remove" affordance — admins only. */
  onRemove?: () => void;
}

const STATUS_LABEL: Record<DeviceStatus, string> = {
  idle: "Idle",
  busy: "Running",
  offline: "Offline",
  error: "Error",
};

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

const STATUS_DOT_CLASS: Record<DeviceStatus, string> = {
  idle: "bg-emerald-500",
  busy: "bg-blue-500 animate-pulse",
  offline: "bg-slate-400",
  error: "bg-red-500",
};

/**
 * One device card with a live progress bar for the running job and the
 * remaining queue listed beneath it.
 *
 * Animation: the parent polls every 2s and replaces the `device` prop. The
 * progress bar binds `width` directly to `progress * 100%`, with a CSS
 * transition so each tick interpolates smoothly. No JS animation loop, no
 * canvas — just CSS.
 */
export function DevicePrintQueue({ device, onRemove }: DevicePrintQueueProps) {
  const job = device.current_job;
  const Icon = TYPE_ICON[device.device_type] ?? CircleAlert;
  const typeLabel = TYPE_LABEL[device.device_type] ?? device.device_type;
  return (
    <div className="rounded-md border bg-background p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-md bg-slate-900 text-white">
            <Icon className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="truncate text-sm font-semibold">{device.name}</p>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {typeLabel}
              </span>
              {device.simulated && (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  sim
                </span>
              )}
            </div>
            <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className={`inline-block h-2 w-2 rounded-full ${STATUS_DOT_CLASS[device.status]}`} />
              {STATUS_LABEL[device.status]}
              <span className="text-slate-300">·</span>
              <span>queue depth {device.queue_depth}</span>
              {device.device_type === "printer_3d" && (
                <>
                  <span className="text-slate-300">·</span>
                  <span>~{Math.round(device.mean_seconds_per_cm3)}s / cm³</span>
                </>
              )}
            </p>
          </div>
        </div>

        {onRemove && (
          <Button
            type="button"
            size="icon-sm"
            variant="outline"
            className="text-destructive hover:bg-destructive/10"
            onClick={onRemove}
            title={`Remove ${device.name}`}
            aria-label={`Remove ${device.name}`}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Progress bar for the running job */}
      <div className="mt-4">
        {job ? (
          <ActiveJobBar job={job} />
        ) : (
          <p className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
            Idle — waiting for the next job.
          </p>
        )}
      </div>

      {/* Queue */}
      {device.queue.length > 0 && (
        <div className="mt-3 space-y-1.5">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Up next
          </p>
          <ul className="space-y-1">
            {device.queue.map((q) => (
              <li
                key={q.id}
                className="flex items-center justify-between rounded-md border border-slate-100 bg-slate-50 px-3 py-1.5 text-xs"
              >
                <span className="font-medium text-slate-700">
                  #{q.queue_position} · {q.label || "Print"}
                </span>
                <span className="text-slate-400">~{formatSeconds(q.simulated_duration_seconds)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ActiveJobBar({ job }: { job: DeviceJob }) {
  const pct = Math.max(0, Math.min(100, job.progress * 100));
  const eta = job.eta_seconds != null ? formatSeconds(job.eta_seconds) : "—";
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="truncate font-medium text-slate-700">
          {job.label || "Active print"}
        </span>
        <span className="tabular-nums text-slate-500">
          {pct.toFixed(0)}% · {eta} left
        </span>
      </div>
      <div className="relative h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-blue-500 transition-[width] duration-[1800ms] ease-linear"
          style={{ width: `${pct}%` }}
        />
        {/* shimmer */}
        <div
          className="pointer-events-none absolute inset-y-0 w-12 -translate-x-full bg-gradient-to-r from-transparent via-white/50 to-transparent animate-[shimmer_1.6s_linear_infinite]"
          style={{ left: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function formatSeconds(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds - m * 60);
  return s === 0 ? `${m}m` : `${m}m ${s}s`;
}
