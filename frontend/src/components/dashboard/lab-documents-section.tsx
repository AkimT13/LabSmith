"use client";

import { useAuth } from "@clerk/nextjs";
import { Download, FileText, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { ConfirmDeleteDialog } from "@/components/dashboard/confirm-delete-dialog";
import { Button } from "@/components/ui/button";
import {
  createLabDocument,
  deleteLabDocument,
  downloadLabDocument,
  fetchLabDocuments,
  type LabDocument,
  type LabRole,
} from "@/lib/api";
import { emitDataChanged, useDataChangedListener } from "@/lib/data-events";
import { toast } from "@/lib/toast";

const INPUT_CLASS =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors focus:border-ring";
const TEXTAREA_CLASS =
  "min-h-32 w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm font-mono outline-none transition-colors focus:border-ring";
const SELECT_CLASS = INPUT_CLASS;
const LABEL_CLASS = "block text-xs font-medium text-muted-foreground";

const CONTENT_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "text/markdown", label: "Markdown (.md)" },
  { value: "text/plain", label: "Plain text (.txt)" },
  { value: "application/json", label: "JSON (.json)" },
];

interface LabDocumentsSectionProps {
  labId: string;
  /** The current user's role in this lab — gates the upload form. */
  userRole: LabRole | null;
}

/**
 * Documents tab inside the Lab Settings dialog. Lists uploaded lab documents
 * and lets `member`/`admin`/`owner` users add new ones via JSON content. The
 * uploaded docs power the M9 onboarding agent's retrieval — they're how an
 * onboarding session can answer "where is the centrifuge?" with a citation.
 */
export function LabDocumentsSection({ labId, userRole }: LabDocumentsSectionProps) {
  const { getToken } = useAuth();
  const [documents, setDocuments] = useState<LabDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<LabDocument | null>(null);

  // Upload form state
  const [title, setTitle] = useState("");
  const [filename, setFilename] = useState("");
  const [contentType, setContentType] = useState("text/markdown");
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const canUpload = userRole === "owner" || userRole === "admin" || userRole === "member";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) {
        setError("No Clerk session token. Sign out and sign back in.");
        return;
      }
      setDocuments(await fetchLabDocuments(token, labId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [getToken, labId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- async data fetch
    load();
  }, [load]);

  useDataChangedListener(load);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim() || !body.trim() || !canUpload) return;
    setSubmitting(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No Clerk session token. Sign out and sign back in.");
      await createLabDocument(token, labId, {
        title: title.trim(),
        content: body,
        source_filename: filename.trim() || null,
        content_type: contentType,
      });
      setTitle("");
      setFilename("");
      setBody("");
      setContentType("text/markdown");
      emitDataChanged();
      toast({
        title: "Document uploaded",
        description: "The onboarding agent can now cite it on the next chat turn.",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDownload(document: LabDocument) {
    setDownloadingId(document.id);
    try {
      const token = await getToken();
      if (!token) throw new Error("No Clerk session token. Sign out and sign back in.");
      await downloadLabDocument(token, document);
    } catch (err) {
      toast({
        title: "Download failed",
        description: err instanceof Error ? err.message : "Could not download document.",
        variant: "destructive",
      });
    } finally {
      setDownloadingId(null);
    }
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    const token = await getToken();
    if (!token) throw new Error("No Clerk session token. Sign out and sign back in.");
    await deleteLabDocument(token, deleteTarget.id);
    emitDataChanged();
    toast({
      title: "Document deleted",
      description: `"${deleteTarget.title}" was removed from the lab.`,
    });
  }

  return (
    <section className="space-y-4 rounded-md border p-4">
      <div className="flex flex-col gap-1">
        <h3 className="flex items-center gap-2 text-base font-semibold">
          <FileText className="h-4 w-4" />
          Lab documents
        </h3>
        <p className="text-sm text-muted-foreground">
          Uploaded SOPs, policies, and onboarding pages. The onboarding agent
          retrieves relevant snippets from these to answer questions in
          onboarding-type sessions.
        </p>
      </div>

      {canUpload && (
        <form className="space-y-3 rounded-md border bg-muted/40 p-3" onSubmit={handleUpload}>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-1.5">
              <label className={LABEL_CLASS} htmlFor="lab-doc-title">
                Title *
              </label>
              <input
                id="lab-doc-title"
                className={INPUT_CLASS}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Microscope SOP — Leica DMi8"
              />
            </div>
            <div className="space-y-1.5">
              <label className={LABEL_CLASS} htmlFor="lab-doc-filename">
                Source filename (optional)
              </label>
              <input
                id="lab-doc-filename"
                className={INPUT_CLASS}
                value={filename}
                onChange={(event) => setFilename(event.target.value)}
                placeholder="microscope-sop.md"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className={LABEL_CLASS} htmlFor="lab-doc-content-type">
              Content type
            </label>
            <select
              id="lab-doc-content-type"
              className={SELECT_CLASS}
              value={contentType}
              onChange={(event) => setContentType(event.target.value)}
            >
              {CONTENT_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className={LABEL_CLASS} htmlFor="lab-doc-body">
              Document text *
            </label>
            <textarea
              id="lab-doc-body"
              className={TEXTAREA_CLASS}
              value={body}
              onChange={(event) => setBody(event.target.value)}
              placeholder="Paste the SOP / protocol / policy here..."
            />
            <p className="text-xs text-muted-foreground">
              Paste the document text here — markdown, plain text, or JSON all
              work, just match the Content type above. Drag-and-drop file
              upload is on the follow-up list.
            </p>
          </div>

          <div className="flex justify-end">
            <Button
              type="submit"
              size="sm"
              className="gap-1"
              disabled={submitting || !title.trim() || !body.trim()}
            >
              <Plus className="h-4 w-4" />
              {submitting ? "Uploading..." : "Upload document"}
            </Button>
          </div>
        </form>
      )}

      {error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-medium uppercase text-muted-foreground">
            {documents.length} document{documents.length === 1 ? "" : "s"}
          </p>
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            onClick={() => void load()}
            disabled={loading}
            aria-label="Refresh documents"
          >
            <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
          </Button>
        </div>

        {loading && documents.length === 0 && (
          <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            Loading documents...
          </p>
        )}

        {!loading && documents.length === 0 && (
          <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            No documents uploaded yet.
            {canUpload
              ? " Upload your first SOP or onboarding doc above."
              : " Ask a lab admin to upload SOPs, equipment guides, or onboarding pages."}
          </p>
        )}

        {documents.map((document) => (
          <div
            key={document.id}
            className="flex items-start justify-between gap-3 rounded-md border p-3"
          >
            <div className="min-w-0 space-y-0.5">
              <p className="truncate text-sm font-medium">{document.title}</p>
              <p className="truncate text-xs text-muted-foreground">
                {document.source_filename || document.content_type}
                {" · "}
                {formatBytes(document.file_size_bytes)}
                {" · uploaded "}
                {new Date(document.created_at).toLocaleDateString()}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="gap-1"
                onClick={() => void handleDownload(document)}
                disabled={downloadingId === document.id}
              >
                <Download className="h-4 w-4" />
                {downloadingId === document.id ? "..." : "Download"}
              </Button>
              {canUpload && (
                <Button
                  type="button"
                  size="icon-sm"
                  variant="outline"
                  className="text-destructive hover:bg-destructive/10"
                  onClick={() => setDeleteTarget(document)}
                  title={`Delete ${document.title}`}
                  aria-label={`Delete ${document.title}`}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>

      {deleteTarget && (
        <ConfirmDeleteDialog
          open={Boolean(deleteTarget)}
          onOpenChange={(open) => !open && setDeleteTarget(null)}
          title={`Delete "${deleteTarget.title}"?`}
          description="This removes the document from the lab and deletes its bytes from storage. Onboarding sessions will no longer be able to cite it."
          onConfirm={handleConfirmDelete}
        />
      )}
    </section>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
