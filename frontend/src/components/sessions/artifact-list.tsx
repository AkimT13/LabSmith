"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { Download, Eye, FileBox, Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchArtifactResponse, type Artifact } from "@/lib/api";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";

interface ArtifactListProps {
  artifacts: Artifact[];
  selectedArtifactId?: string | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void | Promise<void>;
  onSelectArtifact?: (artifact: Artifact) => void;
}

export function ArtifactList({
  artifacts,
  selectedArtifactId = null,
  loading,
  error,
  onRefresh,
  onSelectArtifact,
}: ArtifactListProps) {
  const { getToken } = useAuth();
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  async function handleDownload(artifact: Artifact) {
    if (!artifact.download_url || downloadingId) return;

    setDownloadingId(artifact.id);
    setDownloadError(null);

    try {
      const token = await getToken();
      if (!token) {
        const message = "No Clerk session token. Sign out and sign back in.";
        setDownloadError(message);
        toast({
          title: "Download failed",
          description: message,
          variant: "destructive",
        });
        return;
      }

      const response = await fetchArtifactResponse(token, artifact.download_url);
      const blob = await response.blob();
      const filename = getDownloadFilename(response, artifact);
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
      toast({ title: "Download started", description: filename });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to download artifact";
      setDownloadError(message);
      toast({
        title: "Download failed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <FileBox className="h-4 w-4" />
            Artifacts
          </CardTitle>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => void onRefresh()}
            disabled={loading}
            aria-label="Refresh artifacts"
          >
            <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {error && (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        {downloadError && (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {downloadError}
          </p>
        )}

        {loading && artifacts.length === 0 && (
          <div className="space-y-2" aria-label="Loading artifacts">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        )}

        {!loading && artifacts.length === 0 && (
          <p className="text-sm text-muted-foreground">Generated artifacts will appear here.</p>
        )}

        {artifacts.length > 0 && (
          <div className="max-h-[236px] space-y-2 overflow-y-auto pr-1">
            {artifacts.map((artifact) => (
              <div
                key={artifact.id}
                className={cn(
                  "flex items-start gap-2 rounded-md border p-2 transition",
                  selectedArtifactId === artifact.id && "border-foreground bg-muted/40",
                )}
              >
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left"
                  onClick={() => onSelectArtifact?.(artifact)}
                  disabled={!artifact.preview_url}
                  aria-label={`Preview ${artifact.artifact_type.toUpperCase()} version ${artifact.version}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium">
                        {artifact.artifact_type.toUpperCase()} v{artifact.version}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(artifact.created_at).toLocaleString()}
                      </p>
                    </div>
                    {selectedArtifactId === artifact.id && (
                      <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-background px-2 py-1 text-xs font-medium">
                        <Eye className="h-3 w-3" />
                        Preview
                      </span>
                    )}
                  </div>
                  <ArtifactTrustSummary artifact={artifact} />
                </button>
                <div className="flex shrink-0 items-center gap-2">
                  <span className="rounded-full bg-muted px-2 py-1 text-xs font-medium">
                    {formatFileSize(artifact.file_size_bytes)}
                  </span>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon-sm"
                    onClick={() => void handleDownload(artifact)}
                    disabled={!artifact.download_url || downloadingId !== null}
                    aria-label={`Download ${artifact.artifact_type.toUpperCase()} artifact`}
                  >
                    {downloadingId === artifact.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Download className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ArtifactTrustSummary({ artifact }: { artifact: Artifact }) {
  const printability = artifact.validation?.printability;
  if (!printability) {
    return <p className="mt-2 text-xs text-muted-foreground">No printability report saved.</p>;
  }

  const warningCount = printability.checks.filter((check) => check.status === "warning").length;
  const errorCount = printability.checks.filter((check) => check.status === "error").length;
  const statusLabel =
    errorCount > 0 ? `${errorCount} issue` : warningCount > 0 ? `${warningCount} warning` : "Checks pass";

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <span>
        {printability.dimensions_mm.width} x {printability.dimensions_mm.depth} x{" "}
        {printability.dimensions_mm.height} mm
      </span>
      <span>·</span>
      <span>{printability.material_estimate.mass_g} g PLA est.</span>
      <span>·</span>
      <span>{statusLabel}</span>
    </div>
  );
}

function formatFileSize(value: number | null) {
  if (value === null) return "Pending";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function getDownloadFilename(response: Response, artifact: Artifact): string {
  const contentDisposition = response.headers.get("content-disposition");
  if (contentDisposition) {
    const encodedMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (encodedMatch?.[1]) {
      return decodeURIComponent(encodedMatch[1]);
    }

    const filenameMatch = contentDisposition.match(/filename="([^"]+)"/i);
    if (filenameMatch?.[1]) {
      return filenameMatch[1];
    }
  }

  return `artifact-v${artifact.version}.${extensionForArtifact(artifact)}`;
}

function extensionForArtifact(artifact: Artifact): string {
  if (artifact.artifact_type === "step") return "step";
  if (artifact.artifact_type === "spec_json" || artifact.artifact_type === "validation_json") {
    return "json";
  }
  return "stl";
}
