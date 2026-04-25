import { AlertCircle, AlertTriangle, CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import type { ValidationIssue } from "@/lib/api";

interface ValidationBadgeProps {
  issues: ValidationIssue[];
}

export function ValidationBadge({ issues }: ValidationBadgeProps) {
  const errors = issues.filter((issue) => issue.severity === "error");
  const warnings = issues.filter((issue) => issue.severity === "warning");

  if (errors.length > 0) {
    return (
      <IssueBadge
        tone="error"
        icon={<AlertCircle className="h-3.5 w-3.5" />}
        label={`${errors.length} error${errors.length === 1 ? "" : "s"}`}
      />
    );
  }

  if (warnings.length > 0) {
    return (
      <IssueBadge
        tone="warning"
        icon={<AlertTriangle className="h-3.5 w-3.5" />}
        label={`${warnings.length} warning${warnings.length === 1 ? "" : "s"}`}
      />
    );
  }

  return (
    <IssueBadge
      tone="ok"
      icon={<CheckCircle2 className="h-3.5 w-3.5" />}
      label="Validated"
    />
  );
}

function IssueBadge({
  tone,
  icon,
  label,
}: {
  tone: "ok" | "warning" | "error";
  icon: ReactNode;
  label: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-medium",
        tone === "ok" && "border-emerald-200 bg-emerald-50 text-emerald-700",
        tone === "warning" && "border-amber-200 bg-amber-50 text-amber-800",
        tone === "error" && "border-destructive/30 bg-destructive/10 text-destructive",
      )}
    >
      {icon}
      {label}
    </span>
  );
}
