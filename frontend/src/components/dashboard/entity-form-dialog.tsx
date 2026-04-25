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

const INPUT_CLASS =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors focus:border-ring";
const TEXTAREA_CLASS =
  "min-h-20 w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-ring";
const LABEL_CLASS = "block text-xs font-medium text-muted-foreground";

export interface EntityFormValues {
  name: string;
  description: string;
}

interface EntityFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  submitLabel: string;
  initialValues?: { name: string; description: string };
  onSubmit: (values: EntityFormValues) => Promise<void>;
  nameLabel?: string;
  namePlaceholder?: string;
  descriptionLabel?: string;
  descriptionPlaceholder?: string;
}

export function EntityFormDialog({
  open,
  onOpenChange,
  title,
  description,
  submitLabel,
  initialValues,
  onSubmit,
  nameLabel = "Name",
  namePlaceholder = "Name",
  descriptionLabel = "Description",
  descriptionPlaceholder = "Optional description",
}: EntityFormDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>

        {open && (
          <EntityFormBody
            submitLabel={submitLabel}
            initialValues={initialValues}
            onSubmit={onSubmit}
            onClose={() => onOpenChange(false)}
            nameLabel={nameLabel}
            namePlaceholder={namePlaceholder}
            descriptionLabel={descriptionLabel}
            descriptionPlaceholder={descriptionPlaceholder}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function EntityFormBody({
  submitLabel,
  initialValues,
  onSubmit,
  onClose,
  nameLabel,
  namePlaceholder,
  descriptionLabel,
  descriptionPlaceholder,
}: {
  submitLabel: string;
  initialValues?: { name: string; description: string };
  onSubmit: (values: EntityFormValues) => Promise<void>;
  onClose: () => void;
  nameLabel: string;
  namePlaceholder: string;
  descriptionLabel: string;
  descriptionPlaceholder: string;
}) {
  const [name, setName] = useState(initialValues?.name ?? "");
  const [descriptionValue, setDescriptionValue] = useState(initialValues?.description ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({ name: name.trim(), description: descriptionValue.trim() });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setSubmitting(false);
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <div className="space-y-1.5">
        <label className={LABEL_CLASS} htmlFor="entity-name">
          {nameLabel}
        </label>
        <input
          id="entity-name"
          className={INPUT_CLASS}
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder={namePlaceholder}
          autoFocus
        />
      </div>

      <div className="space-y-1.5">
        <label className={LABEL_CLASS} htmlFor="entity-description">
          {descriptionLabel}
        </label>
        <textarea
          id="entity-description"
          className={TEXTAREA_CLASS}
          value={descriptionValue}
          onChange={(event) => setDescriptionValue(event.target.value)}
          placeholder={descriptionPlaceholder}
        />
      </div>

      {error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting || !name.trim()}>
          {submitting ? "Saving..." : submitLabel}
        </Button>
      </DialogFooter>
    </form>
  );
}
