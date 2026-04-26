"use client";

import { Printer } from "lucide-react";
import { useMemo } from "react";

import { DevicePrintQueue } from "@/components/dashboard/device-print-queue";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLabDevices } from "@/lib/use-lab-devices";

interface LabPrintQueuePanelProps {
  labId: string;
  /**
   * Optional set of artifact IDs from the current session. When provided,
   * any printer working on one of these gets a "Your job is running" badge.
   * Pass an empty array (or omit) when rendering at lab scope — the panel
   * still works, the badge just stays hidden.
   */
  sessionArtifactIds?: string[];
  /** Override the panel header — defaults to "Print queue". */
  title?: string;
  /**
   * When true, render an explicit "no active prints" message instead of
   * auto-hiding the panel. Useful at lab scope where you want a stable card
   * outline; session views prefer auto-hide so the layout stays compact.
   */
  showWhenIdle?: boolean;
}

/**
 * Live print queue for a lab. Renders one device card per printer that has
 * an active job (running OR queued). Polls `useLabDevices` every ~2s, so the
 * progress bar inside each `DevicePrintQueue` ticks live.
 *
 * Used in two places:
 *  - inside a design session (with `sessionArtifactIds` so the agent's print
 *    dispatches get a highlight badge),
 *  - on the lab workspace view (no session, no badge — but still shows
 *    every active device in the lab so you can supervise prints across
 *    multiple sessions from one screen).
 */
export function LabPrintQueuePanel({
  labId,
  sessionArtifactIds = [],
  title = "Print queue",
  showWhenIdle = false,
}: LabPrintQueuePanelProps) {
  const { devices } = useLabDevices(labId);

  const sessionIds = useMemo(() => new Set(sessionArtifactIds), [sessionArtifactIds]);
  const active = devices.filter((d) => d.current_job || d.queue_depth > 0);

  if (active.length === 0 && !showWhenIdle) return null;

  const yourJobActive =
    sessionIds.size > 0 &&
    active.some(
      (d) =>
        (d.current_job && sessionIds.has(d.current_job.artifact_id)) ||
        d.queue.some((j) => sessionIds.has(j.artifact_id)),
    );

  const totalJobs = active.reduce(
    (sum, d) => sum + (d.current_job ? 1 : 0) + d.queue_depth,
    0,
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Printer className="h-4 w-4" />
          {title}
          {yourJobActive && (
            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-blue-700">
              Your job is running
            </span>
          )}
          {active.length > 0 && (
            <span className="ml-auto text-xs font-normal text-muted-foreground">
              {totalJobs} job{totalJobs === 1 ? "" : "s"} across {active.length} printer
              {active.length === 1 ? "" : "s"}
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {active.length === 0 ? (
          <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            No prints in flight. The bar will appear here when the agent
            dispatches a job or you click the printer button on an artifact.
          </p>
        ) : (
          active.map((device) => (
            <DevicePrintQueue key={device.id} device={device} />
          ))
        )}
      </CardContent>
    </Card>
  );
}
