"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ArtifactList } from "@/components/sessions/artifact-list";
import { ChatPanel } from "@/components/sessions/chat-panel";
import { ViewerPanel } from "@/components/sessions/viewer-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  fetchArtifacts,
  fetchLab,
  fetchProject,
  fetchSession,
  type Artifact,
  type DesignSession,
  type Lab,
  type Project,
  type SessionType,
} from "@/lib/api";
import { useDataChangedListener } from "@/lib/data-events";

export default function SessionDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { getToken, isLoaded, isSignedIn } = useAuth();

  const [session, setSession] = useState<DesignSession | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [lab, setLab] = useState<Lab | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [artifactsLoading, setArtifactsLoading] = useState(false);
  const [artifactsError, setArtifactsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!isLoaded || !isSignedIn || !sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) {
        setError("No Clerk session token. Sign out and sign back in.");
        return;
      }
      const loadedSession = await fetchSession(token, sessionId);
      const loadedProject = await fetchProject(token, loadedSession.project_id);
      const loadedLab = await fetchLab(token, loadedProject.laboratory_id);
      setSession(loadedSession);
      setProject(loadedProject);
      setLab(loadedLab);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load session");
    } finally {
      setLoading(false);
    }
  }, [getToken, isLoaded, isSignedIn, sessionId]);

  const loadArtifacts = useCallback(async () => {
    if (!isLoaded || !isSignedIn || !sessionId) return;

    setArtifactsLoading(true);
    setArtifactsError(null);

    try {
      const token = await getToken();
      if (!token) {
        setArtifactsError("No Clerk session token. Sign out and sign back in.");
        return;
      }

      setArtifacts(await fetchArtifacts(token, sessionId));
    } catch (err) {
      setArtifactsError(err instanceof Error ? err.message : "Failed to load artifacts");
    } finally {
      setArtifactsLoading(false);
    }
  }, [getToken, isLoaded, isSignedIn, sessionId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- async data fetch
    load();
  }, [load]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- async data fetch
    loadArtifacts();
  }, [loadArtifacts]);

  const reloadSessionData = useCallback(() => {
    void load();
    void loadArtifacts();
  }, [load, loadArtifacts]);

  useDataChangedListener(reloadSessionData);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading session...</p>
      </div>
    );
  }

  if (error || !session || !project || !lab) {
    return (
      <div className="space-y-4">
        <Button asChild variant="outline" size="sm">
          <Link href="/dashboard/labs">
            <ArrowLeft className="h-4 w-4" />
            Back to labs
          </Link>
        </Button>
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error ?? "Session not found."}
        </p>
      </div>
    );
  }

  const projectHref = `/dashboard/labs?lab=${lab.id}&project=${project.id}`;
  const sessionType = normalizeSessionType(session.session_type);
  const partTypeLabel =
    sessionType === "part_design" && session.part_type ? formatPartType(session.part_type) : null;
  const previewArtifact =
    artifacts.find((artifact) => artifact.artifact_type === "stl" && artifact.preview_url) ?? null;

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Link
            href="/dashboard/labs"
            className="text-muted-foreground hover:text-foreground hover:underline"
          >
            Labs
          </Link>
          <span className="text-muted-foreground">/</span>
          <Link
            href={`/dashboard/labs?lab=${lab.id}`}
            className="text-muted-foreground hover:text-foreground hover:underline"
          >
            {lab.name}
          </Link>
          <span className="text-muted-foreground">/</span>
          <Link
            href={projectHref}
            className="font-medium text-foreground hover:underline"
          >
            {project.name}
          </Link>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <h1 className="truncate text-2xl font-bold tracking-tight">{session.title}</h1>
            <p className="text-sm text-muted-foreground">
              {sessionTypeLabel(sessionType)}
              {partTypeLabel ? ` · ${partTypeLabel}` : ""}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className="rounded-full bg-muted px-3 py-1 text-xs font-medium">
              {session.status}
            </span>
            <Button asChild variant="outline" size="sm">
              <Link href={projectHref}>
                <ArrowLeft className="h-4 w-4" />
                Back to project
              </Link>
            </Button>
          </div>
        </div>
      </div>

      {sessionType === "part_design" ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.9fr)]">
          <ChatPanel
            key={session.id}
            sessionId={session.id}
            initialSpec={session.current_spec}
            disabled={session.status === "archived"}
            disabledReason="Archived sessions are read-only."
            onArtifactGenerated={loadArtifacts}
          />

          <div className="space-y-4">
            <ArtifactList
              artifacts={artifacts}
              loading={artifactsLoading}
              error={artifactsError}
              onRefresh={loadArtifacts}
            />

            <ViewerPanel artifact={previewArtifact} loadingArtifacts={artifactsLoading} />
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {sessionType === "onboarding" && (
            <Card className="border-dashed">
              <CardContent className="py-4">
                <p className="text-sm text-muted-foreground">
                  Onboarding sessions provide general checklist-style guidance
                  until lab document retrieval is connected.
                </p>
              </CardContent>
            </Card>
          )}
          <ChatPanel
            key={session.id}
            sessionId={session.id}
            initialSpec={session.current_spec}
            disabled={session.status === "archived"}
            disabledReason="Archived sessions are read-only."
          />
        </div>
      )}
    </div>
  );
}

function normalizeSessionType(sessionType: string | null | undefined): SessionType {
  if (sessionType === "onboarding" || sessionType === "ONBOARDING") return "onboarding";
  return "part_design";
}

function sessionTypeLabel(sessionType: SessionType): string {
  switch (sessionType) {
    case "part_design":
      return "Part design";
    case "onboarding":
      return "Onboarding";
    default:
      return "Session";
  }
}

function formatPartType(partType: string): string {
  return partType
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}
