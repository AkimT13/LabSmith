"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { ArrowLeft, FolderKanban, FlaskConical, MessageSquare, Rows3 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  fetchLab,
  fetchProject,
  fetchSession,
  type DesignSession,
  type Lab,
  type Project,
} from "@/lib/api";
import { useDataChangedListener } from "@/lib/data-events";

export default function SessionDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { getToken, isLoaded, isSignedIn } = useAuth();

  const [session, setSession] = useState<DesignSession | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [lab, setLab] = useState<Lab | null>(null);
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

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- async data fetch
    load();
  }, [load]);

  useDataChangedListener(load);

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

  return (
    <div className="space-y-6">
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
          className="text-muted-foreground hover:text-foreground hover:underline"
        >
          {project.name}
        </Link>
        <span className="text-muted-foreground">/</span>
        <span className="font-medium">{session.title}</span>
      </div>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase text-muted-foreground">Design session</p>
          <h1 className="text-2xl font-bold tracking-tight">{session.title}</h1>
          <p className="text-sm text-muted-foreground">
            {session.part_type ? `Part type: ${session.part_type}` : "No part type set"}
          </p>
        </div>
        <div className="flex items-center gap-2">
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

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <FlaskConical className="h-4 w-4" />
              Lab
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-medium">{lab.name}</p>
            <p className="text-xs text-muted-foreground">{lab.description || "No description"}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <FolderKanban className="h-4 w-4" />
              Project
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-medium">{project.name}</p>
            <p className="text-xs text-muted-foreground">
              {project.description || "No description"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Rows3 className="h-4 w-4" />
              Session
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-medium">{session.title}</p>
            <p className="text-xs text-muted-foreground">
              Created {new Date(session.created_at).toLocaleString()}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card className="border-dashed">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <MessageSquare className="h-4 w-4" />
            Chat-based design (coming in M3)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            This page will host the chat panel, spec cards, validation badges, and the in-browser
            3D viewer. M3 will wire up SSE streaming and message persistence here.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
