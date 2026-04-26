"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import dynamic from "next/dynamic";
import { AlertTriangle, Box, Loader2, RotateCcw } from "lucide-react";
import type { BufferGeometry } from "three";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchArtifactResponse, type Artifact } from "@/lib/api";

const DynamicStlViewer = dynamic(
  () => import("@/components/sessions/stl-viewer").then((module) => module.StlViewer),
  {
    ssr: false,
    loading: () => <ViewerLoading label="Preparing viewer..." />,
  },
);

interface ViewerPanelProps {
  artifact: Artifact | null;
  loadingArtifacts?: boolean;
}

interface GeometryCache {
  artifactId: string;
  etag: string | null;
  geometry: BufferGeometry;
}

export function ViewerPanel({ artifact, loadingArtifacts = false }: ViewerPanelProps) {
  const { getToken } = useAuth();
  const [geometry, setGeometry] = useState<BufferGeometry | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryNonce, setRetryNonce] = useState(0);
  const cacheRef = useRef<GeometryCache | null>(null);

  const clearGeometry = useCallback(() => {
    setGeometry(null);
    setError(null);
  }, []);

  useEffect(() => {
    return () => {
      cacheRef.current?.geometry.dispose();
      cacheRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!artifact?.preview_url) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- clear stale preview when artifact changes
      clearGeometry();
      return;
    }

    const artifactId = artifact.id;
    const previewUrl = artifact.preview_url;
    const abortController = new AbortController();
    let active = true;

    async function loadPreview() {
      setLoading(true);
      setError(null);

      try {
        const token = await getToken();
        if (!token) {
          throw new Error("No Clerk session token. Sign out and sign back in.");
        }

        const cached =
          cacheRef.current?.artifactId === artifactId ? cacheRef.current : null;
        const response = await fetchArtifactResponse(token, previewUrl, {
          ifNoneMatch: cached?.etag ?? undefined,
          signal: abortController.signal,
        });

        if (!active) return;

        if (response.status === 304 && cached) {
          setGeometry(cached.geometry);
          return;
        }

        const buffer = await response.arrayBuffer();
        const { STLLoader } = await import("three/examples/jsm/loaders/STLLoader.js");
        const nextGeometry = new STLLoader().parse(buffer);
        const previous = cacheRef.current;
        const nextCache: GeometryCache = {
          artifactId,
          etag: response.headers.get("etag"),
          geometry: nextGeometry,
        };

        cacheRef.current = nextCache;
        if (previous && previous.geometry !== nextGeometry) {
          previous.geometry.dispose();
        }

        if (active) {
          setGeometry(nextGeometry);
        } else {
          nextGeometry.dispose();
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (active) {
          setGeometry(null);
          setError(err instanceof Error ? err.message : "Couldn't load preview.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadPreview();

    return () => {
      active = false;
      abortController.abort();
    };
  }, [artifact?.id, artifact?.preview_url, clearGeometry, getToken, retryNonce]);

  return (
    <Card className="min-h-[440px] overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Box className="h-4 w-4" />
            Viewer
          </CardTitle>
          {artifact?.preview_url && (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => setRetryNonce((value) => value + 1)}
              disabled={loading}
              aria-label="Reload preview"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative h-[360px] overflow-hidden rounded-md border bg-muted/30">
          {loadingArtifacts && !artifact && <ViewerLoading label="Loading artifacts..." />}

          {!loadingArtifacts && !artifact && (
            <ViewerEmpty label="Generate a part to see the 3D preview here." />
          )}

          {artifact && !artifact.preview_url && (
            <ViewerEmpty label="No STL preview is available for this artifact." />
          )}

          {artifact?.preview_url && loading && <ViewerLoading label="Loading preview..." />}

          {artifact?.preview_url && error && (
            <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              <p className="max-w-xs text-sm text-muted-foreground">{error}</p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setRetryNonce((value) => value + 1)}
              >
                <RotateCcw className="h-4 w-4" />
                Retry
              </Button>
            </div>
          )}

          {artifact?.preview_url && geometry && !error && !loading && (
            <DynamicStlViewer geometry={geometry} />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ViewerLoading({ label }: { label: string }) {
  return (
    <div className="flex h-full items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </div>
  );
}

function ViewerEmpty({ label }: { label: string }) {
  return (
    <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground">
      {label}
    </div>
  );
}
