import { FileBox, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Artifact } from "@/lib/api";

interface ArtifactListProps {
  artifacts: Artifact[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void | Promise<void>;
}

export function ArtifactList({ artifacts, loading, error, onRefresh }: ArtifactListProps) {
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

        {loading && artifacts.length === 0 && (
          <p className="text-sm text-muted-foreground">Loading artifacts...</p>
        )}

        {!loading && artifacts.length === 0 && (
          <p className="text-sm text-muted-foreground">Generated artifacts will appear here.</p>
        )}

        {artifacts.map((artifact) => (
          <div key={artifact.id} className="rounded-md border p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium">{artifact.artifact_type.toUpperCase()}</p>
                <p className="text-xs text-muted-foreground">
                  Version {artifact.version} · {new Date(artifact.created_at).toLocaleString()}
                </p>
              </div>
              <span className="rounded-full bg-muted px-2 py-1 text-xs font-medium">
                {formatFileSize(artifact.file_size_bytes)}
              </span>
            </div>
            {artifact.file_path && (
              <p className="mt-2 break-all text-xs text-muted-foreground">{artifact.file_path}</p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function formatFileSize(value: number | null) {
  if (value === null) return "Pending";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
