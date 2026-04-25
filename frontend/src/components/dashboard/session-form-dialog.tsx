"use client";

import { useState } from "react";
import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { SessionStatus } from "@/lib/api";

const INPUT_CLASS =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors focus:border-ring";
const SELECT_CLASS =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors focus:border-ring";
const LABEL_CLASS = "block text-xs font-medium text-muted-foreground";

const STATUS_OPTIONS: SessionStatus[] = ["active", "completed", "archived"];

export interface SessionFormValues {
  title: string;
  part_type: string;
  status?: SessionStatus;
}

interface SessionFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  submitLabel: string;
  initialValues?: { title: string; part_type: string; status?: SessionStatus };
  showStatus?: boolean;
  onSubmit: (values: SessionFormValues) => Promise<void>;
}

export function SessionFormDialog({
  open,
  onOpenChange,
  title,
  description,
  submitLabel,
  initialValues,
  showStatus = false,
  onSubmit,
}: SessionFormDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>

        {open && (
          <SessionFormBody
            submitLabel={submitLabel}
            initialValues={initialValues}
            showStatus={showStatus}
            onSubmit={onSubmit}
            onClose={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function SessionFormBody({
  submitLabel,
  initialValues,
  showStatus,
  onSubmit,
  onClose,
}: {
  submitLabel: string;
  initialValues?: { title: string; part_type: string; status?: SessionStatus };
  showStatus: boolean;
  onSubmit: (values: SessionFormValues) => Promise<void>;
  onClose: () => void;
}) {
  const [sessionTitle, setSessionTitle] = useState(initialValues?.title ?? "");
  const [partType, setPartType] = useState(initialValues?.part_type ?? "");
  const [status, setStatus] = useState<SessionStatus>(initialValues?.status ?? "active");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sessionTitle.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        title: sessionTitle.trim(),
        part_type: partType.trim(),
        status: showStatus ? status : undefined,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setSubmitting(false);
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <div className="space-y-1.5">
        <label className={LABEL_CLASS} htmlFor="session-title">
          Session title
        </label>
        <input
          id="session-title"
          className={INPUT_CLASS}
          value={sessionTitle}
          onChange={(event) => setSessionTitle(event.target.value)}
          placeholder="e.g. 96-well plate prototype"
          autoFocus
        />
      </div>

      <div className="space-y-1.5">
        <label className={LABEL_CLASS} htmlFor="session-part-type">
          Part type
        </label>
        <input
          id="session-part-type"
          className={INPUT_CLASS}
          value={partType}
          onChange={(event) => setPartType(event.target.value)}
          placeholder="e.g. tma_mold, tube_rack"
        />
      </div>

      {showStatus && (
        <div className="space-y-1.5">
          <label className={LABEL_CLASS} htmlFor="session-status">
            Status
          </label>
          <select
            id="session-status"
            className={SELECT_CLASS}
            value={status}
            onChange={(event) => setStatus(event.target.value as SessionStatus)}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
      )}

      {error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting || !sessionTitle.trim()}>
          {submitting ? "Saving..." : submitLabel}
        </Button>
      </DialogFooter>
    </form>
  );
}
