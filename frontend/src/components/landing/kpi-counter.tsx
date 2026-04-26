"use client";

import { useEffect, useRef, useState } from "react";

interface KpiCounterProps {
  value: number;
  /** "int" formats whole numbers, "percent" appends % with 2 decimals, "suffix" appends raw suffix */
  format?: "int" | "percent" | "suffix";
  suffix?: string;
  prefix?: string;
  durationMs?: number;
}

/**
 * Counts up from 0 → value when the element enters the viewport.
 * Uses ease-out quartic per the design spec.
 */
export function KpiCounter({
  value,
  format = "int",
  suffix,
  prefix,
  durationMs = 2000,
}: KpiCounterProps) {
  const ref = useRef<HTMLSpanElement | null>(null);
  const [display, setDisplay] = useState(0);
  const startedRef = useRef(false);

  useEffect(() => {
    if (!ref.current) return;
    const node = ref.current;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && !startedRef.current) {
            startedRef.current = true;
            const start = performance.now();
            const tick = (now: number) => {
              const elapsed = now - start;
              const progress = Math.min(1, elapsed / durationMs);
              // ease-out quartic
              const eased = 1 - Math.pow(1 - progress, 4);
              setDisplay(value * eased);
              if (progress < 1) requestAnimationFrame(tick);
              else setDisplay(value);
            };
            requestAnimationFrame(tick);
            observer.disconnect();
          }
        }
      },
      { threshold: 0.4 },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [value, durationMs]);

  const formatted =
    format === "percent"
      ? `${display.toFixed(2)}%`
      : format === "suffix"
        ? `${Math.round(display).toLocaleString()}${suffix ?? ""}`
        : Math.round(display).toLocaleString();

  return (
    <span ref={ref} className="tabular-nums">
      {prefix}
      {formatted}
    </span>
  );
}
