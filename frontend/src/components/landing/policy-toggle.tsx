"use client";

import { useState } from "react";

interface PolicyToggleProps {
  defaultOn?: boolean;
  label: string;
  description?: string;
}

/**
 * 40px pill switch used on the landing page security card.
 * Track turns blue-600 when on; thumb is a white circle with shadow.
 */
export function PolicyToggle({ defaultOn = false, label, description }: PolicyToggleProps) {
  const [on, setOn] = useState(defaultOn);
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-slate-900">{label}</p>
        {description && (
          <p className="mt-0.5 text-xs text-slate-500">{description}</p>
        )}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label={`Toggle ${label}`}
        onClick={() => setOn((v) => !v)}
        className={[
          "relative inline-flex h-6 w-10 shrink-0 items-center rounded-full",
          "transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]",
          "hover:shadow-[0_0_0_4px_rgba(37,99,235,0.12)]",
          on ? "bg-[#2563eb]" : "bg-slate-200",
        ].join(" ")}
      >
        <span
          className={[
            "inline-block h-4 w-4 rounded-full bg-white shadow-sm",
            "transition-transform duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]",
            on ? "translate-x-5" : "translate-x-1",
          ].join(" ")}
        />
      </button>
    </div>
  );
}
