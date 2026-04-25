"use client";

import { useAuth } from "@clerk/nextjs";
import { ChevronRight, FolderKanban, FlaskConical, Plus, Rows3 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { EntityFormDialog } from "@/components/dashboard/entity-form-dialog";
import { Button } from "@/components/ui/button";
import {
  createLab,
  fetchLabs,
  fetchProjects,
  fetchSessions,
  type DesignSession,
  type Lab,
  type Project,
} from "@/lib/api";
import { emitDataChanged, useDataChangedListener } from "@/lib/data-events";
import { cn } from "@/lib/utils";

type ProjectNode = Project & { sessions: DesignSession[] };
type LabNode = Lab & { projects: ProjectNode[] };

export function HierarchySidebar() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeLabId = searchParams.get("lab");
  const activeProjectId = searchParams.get("project");
  const [tree, setTree] = useState<LabNode[]>([]);
  const [openLabIds, setOpenLabIds] = useState<Set<string>>(new Set());
  const [openProjectIds, setOpenProjectIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

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

  const loadTree = useCallback(async () => {
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

      setTree(labNodes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load labs.");
    } finally {
      setLoading(false);
    }
  }, [getToken, isLoaded, isSignedIn]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- async data fetch
    loadTree();
  }, [loadTree, activeLabId, activeProjectId]);

  useDataChangedListener(loadTree);

  function toggleLab(labId: string) {
    setOpenLabIds((current) => toggleId(current, labId));
  }

  function toggleProject(projectId: string) {
    setOpenProjectIds((current) => toggleId(current, projectId));
  }

  async function handleCreateLab(values: { name: string; description: string }) {
    const token = await getToken();
    if (!token) {
      throw new Error("No Clerk session token. Sign out and sign back in.");
    }
    const lab = await createLab(token, {
      name: values.name,
      description: values.description || null,
    });
    emitDataChanged();
    router.push(projectWorkspaceHref(lab.id));
  }

  return (
    <nav className="flex flex-col gap-1 p-3" aria-label="Laboratory hierarchy">
      <div className="flex items-center gap-1">
        <Link
          href="/dashboard/labs"
          className={cn(
            "flex flex-1 items-center gap-2 rounded-md px-3 py-2 text-sm font-medium hover:bg-accent",
            !activeLabId && "bg-accent",
          )}
        >
          <FlaskConical className="h-4 w-4" />
          Laboratories
        </Link>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-8 w-8"
          onClick={() => setCreateOpen(true)}
          aria-label="Create lab"
          title="Create lab"
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>

      <div className="mt-2 space-y-1">
        {loading && <p className="px-3 py-2 text-xs text-muted-foreground">Loading...</p>}
        {error && <p className="px-3 py-2 text-xs text-destructive">{error}</p>}
        {!loading && !error && tree.length === 0 && (
          <p className="px-3 py-2 text-xs text-muted-foreground">
            No labs yet. Click + to create one.
          </p>
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
                  href={projectWorkspaceHref(lab.id)}
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
                            href={projectWorkspaceHref(lab.id, project.id)}
                            className={cn(
                              "flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent",
                              isActiveProject && "bg-accent font-medium",
                            )}
                          >
                            <FolderKanban className="h-4 w-4 shrink-0" />
                            <span className="truncate">{project.name}</span>
                          </Link>
                        </div>

                        {isProjectOpen && (
                          <div className="ml-3 space-y-1 border-l pl-3">
                            {project.sessions.map((session) => (
                              <div
                                key={session.id}
                                className="flex min-w-0 items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground"
                              >
                                <Rows3 className="h-4 w-4 shrink-0" />
                                <span className="truncate">{session.title}</span>
                              </div>
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

      <EntityFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        title="Create laboratory"
        description="Labs are the top-level workspace. You'll be the owner."
        submitLabel="Create lab"
        onSubmit={handleCreateLab}
        nameLabel="Lab name"
        namePlaceholder="e.g. Curry Lab"
        descriptionPlaceholder="What does this lab work on?"
      />
    </nav>
  );
}

function projectWorkspaceHref(labId: string, projectId?: string): string {
  const params = new URLSearchParams({ lab: labId });
  if (projectId) params.set("project", projectId);
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
