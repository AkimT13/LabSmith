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
import type { SessionStatus, SessionType } from "@/lib/api";

const INPUT_CLASS =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors focus:border-ring";
const SELECT_CLASS =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors focus:border-ring";
const LABEL_CLASS = "block text-xs font-medium text-muted-foreground";

const STATUS_OPTIONS: SessionStatus[] = ["active", "completed", "archived"];

interface SessionTypeOption {
  value: SessionType;
  label: string;
  description: string;
}

const SESSION_TYPE_OPTIONS: SessionTypeOption[] = [
  {
    value: "part_design",
    label: "Part design",
    description:
      "Describe a 3D-printable lab part in natural language. The agent extracts a spec, validates it, and generates an STL.",
  },
  {
    value: "onboarding",
    label: "Onboarding",
    description:
      "Help a new lab member get oriented with practical checklist-style guidance.",
  },
];

export interface SessionFormValues {
  title: string;
  session_type: SessionType;
  part_type: string;
  status?: SessionStatus;
}

interface SessionFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  submitLabel: string;
  initialValues?: {
    title: string;
    session_type?: SessionType;
    part_type: string;
    status?: SessionStatus;
  };
  /** When true, the session-type picker is shown. Hidden in edit mode because
   * session_type is immutable after creation. */
  showSessionType?: boolean;
  /** When true, the status select is shown. Hidden in create mode (always active). */
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
  showSessionType = false,
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
            showSessionType={showSessionType}
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
  showSessionType,
  showStatus,
  onSubmit,
  onClose,
}: {
  submitLabel: string;
  initialValues?: {
    title: string;
    session_type?: SessionType;
    part_type: string;
    status?: SessionStatus;
  };
  showSessionType: boolean;
  showStatus: boolean;
  onSubmit: (values: SessionFormValues) => Promise<void>;
  onClose: () => void;
}) {
  const [sessionTitle, setSessionTitle] = useState(initialValues?.title ?? "");
  const [sessionType, setSessionType] = useState<SessionType>(
    initialValues?.session_type ?? "part_design",
  );
  const [partType, setPartType] = useState(initialValues?.part_type ?? "");
  const [status, setStatus] = useState<SessionStatus>(initialValues?.status ?? "active");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Part type only applies to part_design sessions. If the user picks
  // onboarding the part_type field is irrelevant — hide it instead of
  // silently dropping the value.
  const showPartType = sessionType === "part_design";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sessionTitle.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        title: sessionTitle.trim(),
        session_type: sessionType,
        part_type: showPartType ? partType.trim() : "",
        status: showStatus ? status : undefined,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setSubmitting(false);
    }
  }

  const activeOption = SESSION_TYPE_OPTIONS.find((opt) => opt.value === sessionType);

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

      {showSessionType && (
        <div className="space-y-1.5">
          <label className={LABEL_CLASS} htmlFor="session-type">
            Session type
          </label>
          <select
            id="session-type"
            className={SELECT_CLASS}
            value={sessionType}
            onChange={(event) => setSessionType(event.target.value as SessionType)}
          >
            {SESSION_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {activeOption && (
            <p className="text-xs text-muted-foreground">{activeOption.description}</p>
          )}
        </div>
      )}

      {showPartType && (
        <div className="space-y-1.5">
          <label className={LABEL_CLASS} htmlFor="session-part-type">
            Part type
          </label>
          <input
            id="session-part-type"
            className={INPUT_CLASS}
            value={partType}
            onChange={(event) => setPartType(event.target.value)}
            placeholder="e.g. tube_rack, gel_comb"
          />
        </div>
      )}

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
