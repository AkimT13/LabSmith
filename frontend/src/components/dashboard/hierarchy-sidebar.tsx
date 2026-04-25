"use client";

import { useAuth } from "@clerk/nextjs";
import { ChevronRight, FolderKanban, FlaskConical, Rows3 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  fetchLabs,
  fetchProjects,
  fetchSessions,
  type DesignSession,
  type Lab,
  type Project,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type ProjectNode = Project & { sessions: DesignSession[] };
type LabNode = Lab & { projects: ProjectNode[] };

export function HierarchySidebar() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const searchParams = useSearchParams();
  const activeLabId = searchParams.get("lab");
  const activeProjectId = searchParams.get("project");
  const activeSessionId = searchParams.get("session");
  const [tree, setTree] = useState<LabNode[]>([]);
  const [openLabIds, setOpenLabIds] = useState<Set<string>>(new Set());
  const [openProjectIds, setOpenProjectIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const visibleOpenLabIds = useMemo(() => {
    const next = new Set(openLabIds);
    if (activeLabId) next.add(activeLabId);
    return next;
  }, [activeLabId, openLabIds]);

  const visibleOpenProjectIds = useMemo(() => {
    const next = new Set(openProjectIds);
    if (activeProjectId) next.add(activeProjectId);
    return next;
  }, [activeProjectId, openProjectIds]);

  useEffect(() => {
    let ignore = false;

    async function loadTree() {
      if (!isLoaded) return;

      if (!isSignedIn) {
        setTree([]);
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const token = await getToken();
        if (!token) {
          setTree([]);
          setError("Sign in to load labs.");
          return;
        }

        const labs = await fetchLabs(token);
        const labNodes = await Promise.all(
          labs.map(async (lab) => {
            const projects = await fetchProjects(token, lab.id);
            const projectNodes = await Promise.all(
              projects.map(async (project) => ({
                ...project,
                sessions: await fetchSessions(token, project.id),
              })),
            );

            return { ...lab, projects: projectNodes };
          }),
        );

        if (!ignore) {
          setTree(labNodes);
        }
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Unable to load labs.");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    loadTree();

    return () => {
      ignore = true;
    };
  }, [activeLabId, activeProjectId, activeSessionId, getToken, isLoaded, isSignedIn]);

  function toggleLab(labId: string) {
    setOpenLabIds((current) => toggleId(current, labId));
  }

  function toggleProject(projectId: string) {
    setOpenProjectIds((current) => toggleId(current, projectId));
  }

  return (
    <nav className="flex flex-col gap-1 p-3" aria-label="Laboratory hierarchy">
      <Link
        href="/dashboard/labs"
        className={cn(
          "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium hover:bg-accent",
          !activeLabId && "bg-accent",
        )}
      >
        <FlaskConical className="h-4 w-4" />
        Laboratories
      </Link>

      <div className="mt-2 space-y-1">
        {loading && <p className="px-3 py-2 text-xs text-muted-foreground">Loading...</p>}
        {error && <p className="px-3 py-2 text-xs text-destructive">{error}</p>}
        {!loading && !error && tree.length === 0 && (
          <p className="px-3 py-2 text-xs text-muted-foreground">No labs yet.</p>
        )}

        {tree.map((lab) => {
          const isLabOpen = visibleOpenLabIds.has(lab.id);
          const isActiveLab = activeLabId === lab.id;

          return (
            <div key={lab.id} className="space-y-1">
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
                  aria-label={`${isLabOpen ? "Collapse" : "Expand"} ${lab.name}`}
                  onClick={() => toggleLab(lab.id)}
                >
                  <ChevronRight
                    className={cn("h-4 w-4 transition-transform", isLabOpen && "rotate-90")}
                  />
                </button>
                <Link
                  href={workspaceHref(lab.id)}
                  className={cn(
                    "flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent",
                    isActiveLab && !activeProjectId && "bg-accent font-medium",
                  )}
                >
                  <FlaskConical className="h-4 w-4 shrink-0" />
                  <span className="truncate">{lab.name}</span>
                </Link>
              </div>

              {isLabOpen && (
                <div className="ml-3 space-y-1 border-l pl-3">
                  {lab.projects.map((project) => {
                    const isProjectOpen = visibleOpenProjectIds.has(project.id);
                    const isActiveProject = activeProjectId === project.id;

                    return (
                      <div key={project.id} className="space-y-1">
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
                            aria-label={`${isProjectOpen ? "Collapse" : "Expand"} ${
                              project.name
                            }`}
                            onClick={() => toggleProject(project.id)}
                          >
                            <ChevronRight
                              className={cn(
                                "h-4 w-4 transition-transform",
                                isProjectOpen && "rotate-90",
                              )}
                            />
                          </button>
                          <Link
                            href={workspaceHref(lab.id, project.id)}
                            className={cn(
                              "flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent",
                              isActiveProject && !activeSessionId && "bg-accent font-medium",
                            )}
                          >
                            <FolderKanban className="h-4 w-4 shrink-0" />
                            <span className="truncate">{project.name}</span>
                          </Link>
                        </div>

                        {isProjectOpen && (
                          <div className="ml-3 space-y-1 border-l pl-3">
                            {project.sessions.map((session) => (
                              <Link
                                key={session.id}
                                href={workspaceHref(lab.id, project.id, session.id)}
                                className={cn(
                                  "flex min-w-0 items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent",
                                  activeSessionId === session.id && "bg-accent font-medium",
                                )}
                              >
                                <Rows3 className="h-4 w-4 shrink-0" />
                                <span className="truncate">{session.title}</span>
                              </Link>
                            ))}
                            {project.sessions.length === 0 && (
                              <p className="px-2 py-1 text-xs text-muted-foreground">
                                No sessions.
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {lab.projects.length === 0 && (
                    <p className="px-2 py-1 text-xs text-muted-foreground">No projects.</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </nav>
  );
}

function workspaceHref(labId: string, projectId?: string, sessionId?: string): string {
  const params = new URLSearchParams({ lab: labId });
  if (projectId) params.set("project", projectId);
  if (sessionId) params.set("session", sessionId);
  return `/dashboard/labs?${params.toString()}`;
}

function toggleId(current: Set<string>, id: string): Set<string> {
  const next = new Set(current);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  return next;
}
