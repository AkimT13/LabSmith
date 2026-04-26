"use client";

import type {
  AutoclaveResult,
  CentrifugeResult,
  DeviceJobResult,
  LiquidHandlerResult,
  PlateReaderResult,
  ThermocyclerResult,
} from "@/lib/api";

interface DeviceResultCardProps {
  result: DeviceJobResult;
}

/**
 * Renders a per-device-type post-completion report. Dispatches on
 * `result.kind` to a small visualization plus a metrics row. Falls back
 * to a text-only summary for unknown kinds (printer jobs, future device
 * types) so the timeline never renders nothing.
 */
export function DeviceResultCard({ result }: DeviceResultCardProps) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="mb-2 flex items-baseline gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Result
        </p>
        <p className="text-xs text-slate-700">{result.headline}</p>
      </div>

      <Visualization result={result} />

      <MetricsRow metrics={result.metrics} />
    </div>
  );
}

function Visualization({ result }: { result: DeviceJobResult }) {
  if (result.kind === "plate_reader") {
    return <PlateHeatmap result={result as PlateReaderResult} />;
  }
  if (result.kind === "thermocycler") {
    return <ThermocyclerChart result={result as ThermocyclerResult} />;
  }
  if (result.kind === "centrifuge") {
    return <CentrifugeRing result={result as CentrifugeResult} />;
  }
  if (result.kind === "liquid_handler") {
    return <LiquidHandlerGrid result={result as LiquidHandlerResult} />;
  }
  if (result.kind === "autoclave") {
    return <AutoclaveTrace result={result as AutoclaveResult} />;
  }
  return null;
}

function MetricsRow({ metrics }: { metrics: Record<string, string | number> }) {
  const entries = Object.entries(metrics).slice(0, 6);
  if (entries.length === 0) return null;
  return (
    <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] sm:grid-cols-3">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-baseline justify-between gap-2">
          <span className="truncate text-slate-500">
            {key.replace(/_/g, " ")}
          </span>
          <span className="font-mono font-medium text-slate-800">{String(value)}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Plate-reader heatmap — the crown jewel
// ---------------------------------------------------------------------------

function PlateHeatmap({ result }: { result: PlateReaderResult }) {
  const flat = result.grid.flat();
  const min = Math.min(...flat);
  const max = Math.max(...flat);
  const range = Math.max(0.001, max - min);
  return (
    <div className="space-y-1.5">
      <div
        className="grid gap-[2px]"
        style={{
          gridTemplateColumns: `repeat(${result.cols}, minmax(0, 1fr))`,
        }}
      >
        {result.grid.flatMap((row, r) =>
          row.map((value, c) => (
            <div
              key={`${r}-${c}`}
              title={`${rowLabel(r)}${c + 1}: ${value}`}
              className="aspect-square rounded-[2px]"
              style={{ backgroundColor: heatColor((value - min) / range) }}
            />
          )),
        )}
      </div>
      <div className="flex items-center justify-between text-[10px] text-slate-500">
        <span className="font-mono">low {min.toFixed(2)}</span>
        <HeatmapLegend />
        <span className="font-mono">high {max.toFixed(2)}</span>
      </div>
    </div>
  );
}

function HeatmapLegend() {
  return (
    <div className="flex h-2 w-24 overflow-hidden rounded-full">
      {Array.from({ length: 24 }).map((_, i) => (
        <div
          key={i}
          className="flex-1"
          style={{ backgroundColor: heatColor(i / 23) }}
        />
      ))}
    </div>
  );
}

function rowLabel(rowIndex: number): string {
  return String.fromCharCode(65 + rowIndex);
}

function heatColor(t: number): string {
  // Linear blend through a viridis-ish ramp: deep navy → teal → yellow.
  const stops = [
    [11, 19, 43],     // navy
    [44, 80, 121],    // blue
    [38, 130, 142],   // teal
    [120, 200, 130],  // green
    [253, 231, 37],   // yellow
  ];
  const clamped = Math.max(0, Math.min(1, t));
  const scaled = clamped * (stops.length - 1);
  const idx = Math.floor(scaled);
  const frac = scaled - idx;
  const a = stops[idx];
  const b = stops[Math.min(stops.length - 1, idx + 1)];
  const r = Math.round(a[0] + (b[0] - a[0]) * frac);
  const g = Math.round(a[1] + (b[1] - a[1]) * frac);
  const bl = Math.round(a[2] + (b[2] - a[2]) * frac);
  return `rgb(${r}, ${g}, ${bl})`;
}

// ---------------------------------------------------------------------------
// Thermocycler temperature trace
// ---------------------------------------------------------------------------

function ThermocyclerChart({ result }: { result: ThermocyclerResult }) {
  if (!result.trace.length) return null;
  const width = 300;
  const height = 80;
  const xs = result.trace.map((p) => p.t);
  const ys = result.trace.map((p) => p.temp);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys, 0);
  const maxY = Math.max(...ys, 100);
  const xRange = Math.max(0.001, maxX - minX);
  const yRange = Math.max(0.001, maxY - minY);
  const points = result.trace
    .map(
      (p) =>
        `${((p.t - minX) / xRange) * width},${
          height - ((p.temp - minY) / yRange) * height
        }`,
    )
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-20 w-full"
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id="cyclerFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#dbeafe" />
          <stop offset="100%" stopColor="#dbeafe" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon
        points={`0,${height} ${points} ${width},${height}`}
        fill="url(#cyclerFill)"
      />
      <polyline
        points={points}
        fill="none"
        stroke="#2563eb"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Centrifuge — animated ring with quality color
// ---------------------------------------------------------------------------

function CentrifugeRing({ result }: { result: CentrifugeResult }) {
  const score = Number(result.metrics.pellet_score ?? 70);
  const quality = String(result.metrics.pellet_quality ?? "tight");
  const color =
    quality === "tight" ? "#16a34a" : quality === "loose" ? "#d97706" : "#dc2626";
  const stroke = 6;
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.min(1, Math.max(0, score / 100)));
  return (
    <div className="flex items-center gap-3">
      <svg width="68" height="68" viewBox="0 0 68 68">
        <circle
          cx="34"
          cy="34"
          r={radius}
          stroke="#e2e8f0"
          strokeWidth={stroke}
          fill="none"
        />
        <circle
          cx="34"
          cy="34"
          r={radius}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 34 34)"
        />
        <text
          x="34"
          y="38"
          textAnchor="middle"
          fontSize="13"
          fontWeight="600"
          fill="#0f172a"
        >
          {score}
        </text>
      </svg>
      <div className="text-xs text-slate-600">
        Pellet score (0–100). Higher = tighter. Tracks RCF × time vs. tube
        density.
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Liquid handler — dispense pattern grid
// ---------------------------------------------------------------------------

function LiquidHandlerGrid({ result }: { result: LiquidHandlerResult }) {
  return (
    <div
      className="grid gap-[2px]"
      style={{
        gridTemplateColumns: `repeat(${result.cols}, minmax(0, 1fr))`,
      }}
    >
      {result.grid.flatMap((row, r) =>
        row.map((dispensed, c) => (
          <div
            key={`${r}-${c}`}
            title={`${rowLabel(r)}${c + 1}: ${dispensed ? "dispensed" : "skipped"}`}
            className={[
              "aspect-square rounded-[2px]",
              dispensed ? "bg-blue-500" : "bg-slate-200",
            ].join(" ")}
          />
        )),
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Autoclave temperature trace (re-uses the chart shape)
// ---------------------------------------------------------------------------

function AutoclaveTrace({ result }: { result: AutoclaveResult }) {
  if (!result.trace.length) return null;
  const width = 300;
  const height = 80;
  const xs = result.trace.map((p) => p.t);
  const ys = result.trace.map((p) => p.temp);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys, 0);
  const maxY = Math.max(...ys, 130);
  const xRange = Math.max(0.001, maxX - minX);
  const yRange = Math.max(0.001, maxY - minY);
  const points = result.trace
    .map(
      (p) =>
        `${((p.t - minX) / xRange) * width},${
          height - ((p.temp - minY) / yRange) * height
        }`,
    )
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-20 w-full"
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id="autoclaveFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#fee2e2" />
          <stop offset="100%" stopColor="#fee2e2" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon
        points={`0,${height} ${points} ${width},${height}`}
        fill="url(#autoclaveFill)"
      />
      <polyline
        points={points}
        fill="none"
        stroke="#dc2626"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
