"use client";

import { useAuth } from "@clerk/nextjs";
import { Plus, Printer, Trash2 } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { ConfirmDeleteDialog } from "@/components/dashboard/confirm-delete-dialog";
import { DevicePrintQueue } from "@/components/dashboard/device-print-queue";
import { Button } from "@/components/ui/button";
import {
  createLabDevice,
  deleteLabDevice,
  DEVICE_TYPE_OPTIONS,
  type DeviceType,
  type LabDevice,
  type LabRole,
} from "@/lib/api";
import { emitDataChanged } from "@/lib/data-events";
import { toast } from "@/lib/toast";
import { useLabDevices } from "@/lib/use-lab-devices";

const INPUT_CLASS =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors focus:border-ring";
const LABEL_CLASS = "block text-xs font-medium text-muted-foreground";

interface LabDevicesSectionProps {
  labId: string;
  userRole: LabRole | null;
}

/**
 * Devices tab inside Lab Settings. Lets admins add/remove simulated 3D
 * printers and exposes the live print queue. Only `admin`/`owner` can
 * add/remove; `member`/`viewer` can see the queue.
 */
export function LabDevicesSection({ labId, userRole }: LabDevicesSectionProps) {
  const { getToken } = useAuth();
  const { devices, loading, error, refresh } = useLabDevices(labId);

  const canManage = userRole === "owner" || userRole === "admin";

  const [name, setName] = useState("");
  const [deviceType, setDeviceType] = useState<DeviceType>("printer_3d");
  const [meanSeconds, setMeanSeconds] = useState("12");
  const [submitting, setSubmitting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<LabDevice | null>(null);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim() || !canManage) return;
    setSubmitting(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("No Clerk session token. Sign out and sign back in.");
      const seconds = Number.parseFloat(meanSeconds);
      await createLabDevice(token, labId, {
        name: name.trim(),
        device_type: deviceType,
        mean_seconds_per_cm3: Number.isFinite(seconds) && seconds > 0 ? seconds : 12,
      });
      setName("");
      setDeviceType("printer_3d");
      setMeanSeconds("12");
      emitDataChanged();
      await refresh();
      toast({
        title: "Device added",
        description: "The agent can now route print jobs to it.",
      });
    } catch (err) {
      toast({
        title: "Add device failed",
        description: err instanceof Error ? err.message : "Could not create device.",
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    const token = await getToken();
    if (!token) throw new Error("No Clerk session token. Sign out and sign back in.");
    await deleteLabDevice(token, deleteTarget.id);
    emitDataChanged();
    await refresh();
    toast({
      title: "Device removed",
      description: `"${deleteTarget.name}" was disconnected from the lab.`,
    });
  }

  return (
    <section className="space-y-4 rounded-md border p-4">
      <div className="flex flex-col gap-1">
        <h3 className="flex items-center gap-2 text-base font-semibold">
          <Printer className="h-4 w-4" />
          Lab devices
        </h3>
        <p className="text-sm text-muted-foreground">
          Add simulated 3D printers to this lab. The chat agent dispatches print
          jobs to them automatically — when multiple are connected, jobs are
          balanced across the shortest queue. Real device adapters slot in
          behind the same protocol later.
        </p>
      </div>

      {canManage && (
        <form
          className="space-y-3 rounded-md border bg-muted/40 p-3"
          onSubmit={handleCreate}
        >
          <div className="grid gap-3 md:grid-cols-[1fr_180px]">
            <div className="space-y-1.5">
              <label className={LABEL_CLASS} htmlFor="lab-device-name">
                Name *
              </label>
              <input
                id="lab-device-name"
                className={INPUT_CLASS}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Bench Prusa MK4 / Cent A / Bio-Rad C1000"
              />
            </div>
            <div className="space-y-1.5">
              <label className={LABEL_CLASS} htmlFor="lab-device-type">
                Device type *
              </label>
              <select
                id="lab-device-type"
                className={INPUT_CLASS}
                value={deviceType}
                onChange={(event) => setDeviceType(event.target.value as DeviceType)}
              >
                {DEVICE_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-muted-foreground">
                {DEVICE_TYPE_OPTIONS.find((o) => o.value === deviceType)?.hint}
              </p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-[180px_auto]">
            {deviceType === "printer_3d" && (
              <div className="space-y-1.5">
                <label className={LABEL_CLASS} htmlFor="lab-device-speed">
                  Sim speed (sec / cm³)
                </label>
                <input
                  id="lab-device-speed"
                  type="number"
                  min={1}
                  step={0.5}
                  className={INPUT_CLASS}
                  value={meanSeconds}
                  onChange={(event) => setMeanSeconds(event.target.value)}
                />
              </div>
            )}
            <div className="flex items-end">
              <Button
                type="submit"
                size="sm"
                className="gap-1"
                disabled={submitting || !name.trim()}
              >
                <Plus className="h-4 w-4" />
                {submitting ? "Adding..." : "Add device"}
              </Button>
            </div>
          </div>
        </form>
      )}

      {error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="space-y-2">
        <p className="text-xs font-medium uppercase text-muted-foreground">
          {devices.length} device{devices.length === 1 ? "" : "s"}
        </p>

        {loading && devices.length === 0 && (
          <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            Loading devices...
          </p>
        )}

        {!loading && devices.length === 0 && (
          <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            No devices yet.
            {canManage
              ? " Add a simulated printer above so the agent has somewhere to send print jobs."
              : " Ask a lab admin to add a printer."}
          </p>
        )}

        <div className="grid gap-3">
          {devices.map((device) => (
            <DevicePrintQueue
              key={device.id}
              device={device}
              onRemove={canManage ? () => setDeleteTarget(device) : undefined}
            />
          ))}
        </div>
      </div>

      {deleteTarget && (
        <ConfirmDeleteDialog
          open={Boolean(deleteTarget)}
          onOpenChange={(open) => !open && setDeleteTarget(null)}
          title={`Remove "${deleteTarget.name}"?`}
          description="Disconnects this printer from the lab. Any active or queued jobs on it will be removed."
          onConfirm={handleConfirmDelete}
        />
      )}
    </section>
  );
}

// Separate icon-only delete button used inline; kept here so the section file
// is the single import point for callers.
export function DeviceTrashButton({ onClick }: { onClick: () => void }) {
  return (
    <Button
      type="button"
      size="icon-sm"
      variant="outline"
      className="text-destructive hover:bg-destructive/10"
      onClick={onClick}
      title="Remove device"
      aria-label="Remove device"
    >
      <Trash2 className="h-4 w-4" />
    </Button>
  );
}
