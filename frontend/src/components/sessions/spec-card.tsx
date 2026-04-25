import { Box, Loader2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ValidationBadge } from "@/components/sessions/validation-badge";
import type { GenerationState } from "@/lib/use-chat";
import type { PartRequest, ValidationIssue } from "@/lib/api";

interface SpecCardProps {
  spec: PartRequest | null;
  validationIssues: ValidationIssue[];
  generation: GenerationState;
}

const specFields: Array<{ key: keyof PartRequest; label: string; suffix?: string }> = [
  { key: "rows", label: "Rows" },
  { key: "cols", label: "Columns" },
  { key: "well_count", label: "Well count" },
  { key: "diameter_mm", label: "Diameter", suffix: "mm" },
  { key: "spacing_mm", label: "Spacing", suffix: "mm" },
  { key: "depth_mm", label: "Depth", suffix: "mm" },
  { key: "well_width_mm", label: "Well width", suffix: "mm" },
  { key: "well_height_mm", label: "Well height", suffix: "mm" },
  { key: "tube_volume_ml", label: "Tube volume", suffix: "mL" },
];

export function SpecCard({ spec, validationIssues, generation }: SpecCardProps) {
  if (!spec) return null;

  const visibleFields = specFields.filter(({ key }) => spec[key] !== null);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Box className="h-4 w-4" />
            Parsed spec
          </CardTitle>
          <ValidationBadge issues={validationIssues} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <SpecRow label="Part type" value={formatPartType(spec.part_type)} />
          {visibleFields.map(({ key, label, suffix }) => (
            <SpecRow
              key={key}
              label={label}
              value={`${spec[key]}${suffix ? ` ${suffix}` : ""}`}
            />
          ))}
        </div>

        {spec.notes.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase text-muted-foreground">Notes</p>
            <ul className="space-y-1 text-sm text-muted-foreground">
              {spec.notes.map((note) => (
                <li key={note} className="break-words">
                  {note}
                </li>
              ))}
            </ul>
          </div>
        )}

        {validationIssues.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase text-muted-foreground">Validation</p>
            <div className="space-y-2">
              {validationIssues.map((issue) => (
                <div key={`${issue.code}-${issue.field ?? "root"}`} className="rounded-md border p-2">
                  <p className="text-sm font-medium">{issue.message}</p>
                  <p className="text-xs text-muted-foreground">
                    {issue.field ? `${issue.field} · ${issue.code}` : issue.code}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {generation.status !== "idle" && (
          <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm">
            {generation.status === "generating" && (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating {generation.template ? formatPartType(generation.template) : "artifact"}
              </span>
            )}
            {generation.status === "complete" && (
              <span>
                Generated {generation.artifactType?.toUpperCase() ?? "artifact"} version{" "}
                {generation.version ?? 1}
              </span>
            )}
            {generation.status === "error" && <span>Generation stopped</span>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SpecRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-muted/30 px-3 py-2">
      <p className="text-[11px] font-medium uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-medium">{value}</p>
    </div>
  );
}

function formatPartType(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
