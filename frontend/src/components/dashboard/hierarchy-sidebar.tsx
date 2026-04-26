"use client";

import { useAuth } from "@clerk/nextjs";
import { ChevronRight, FolderKanban, FlaskConical, Plus, Rows3 } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { EntityFormDialog } from "@/components/dashboard/entity-form-dialog";
import {
  SessionFormDialog,
  type SessionFormValues,
} from "@/components/dashboard/session-form-dialog";
import { Button } from "@/components/ui/button";
import {
  createLab,
  createProject,
  createSession,
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
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeLabId = searchParams.get("lab");
  const activeProjectId = searchParams.get("project");
  const activeSessionId = pathname.match(/^\/dashboard\/sessions\/([^/]+)/)?.[1] ?? null;
  const [tree, setTree] = useState<LabNode[]>([]);
  const [openLabIds, setOpenLabIds] = useState<Set<string>>(new Set());
  const [openProjectIds, setOpenProjectIds] = useState<Set<string>>(new Set());
  const [collapsedLabIds, setCollapsedLabIds] = useState<Set<string>>(new Set());
  const [collapsedProjectIds, setCollapsedProjectIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createProjectLab, setCreateProjectLab] = useState<LabNode | null>(null);
  const [createSessionTarget, setCreateSessionTarget] = useState<{
    lab: LabNode;
    project: ProjectNode;
  } | null>(null);

  const activeSessionLocation = findSessionLocation(tree, activeSessionId);
  const activeSessionLabId = activeSessionLocation?.labId ?? null;
  const activeSessionProjectId = activeSessionLocation?.projectId ?? null;

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
  }, [getToken, isLoaded, isSignedIn, setError, setLoading, setTree]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- async data fetch
    loadTree();
  }, [loadTree, activeLabId, activeProjectId]);

  useDataChangedListener(loadTree);

  function labIsOpen(labId: string) {
    const routeKeepsOpen = activeLabId === labId || activeSessionLabId === labId;
    return (openLabIds.has(labId) || routeKeepsOpen) && !collapsedLabIds.has(labId);
  }

  function projectIsOpen(projectId: string) {
    const routeKeepsOpen = activeProjectId === projectId || activeSessionProjectId === projectId;
    return (
      (openProjectIds.has(projectId) || routeKeepsOpen) && !collapsedProjectIds.has(projectId)
    );
  }

  function toggleLab(labId: string) {
    if (labIsOpen(labId)) {
      setOpenLabIds((current) => removeId(current, labId));
      setCollapsedLabIds((current) => addId(current, labId));
      return;
    }

    setCollapsedLabIds((current) => removeId(current, labId));
    setOpenLabIds((current) => addId(current, labId));
  }

  function toggleProject(projectId: string) {
    if (projectIsOpen(projectId)) {
      setOpenProjectIds((current) => removeId(current, projectId));
      setCollapsedProjectIds((current) => addId(current, projectId));
      return;
    }

    setCollapsedProjectIds((current) => removeId(current, projectId));
    setOpenProjectIds((current) => addId(current, projectId));
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

  async function handleCreateProject(values: { name: string; description: string }) {
    if (!createProjectLab) return;
    const token = await getToken();
    if (!token) {
      throw new Error("No Clerk session token. Sign out and sign back in.");
    }

    const project = await createProject(token, createProjectLab.id, {
      name: values.name,
      description: values.description || null,
    });
    setOpenLabIds((current) => addId(current, createProjectLab.id));
    setCollapsedLabIds((current) => removeId(current, createProjectLab.id));
    emitDataChanged();
    router.push(projectWorkspaceHref(createProjectLab.id, project.id));
  }

  async function handleCreateSession(values: SessionFormValues) {
    if (!createSessionTarget) return;
    const token = await getToken();
    if (!token) {
      throw new Error("No Clerk session token. Sign out and sign back in.");
    }

    const session = await createSession(token, createSessionTarget.project.id, {
      title: values.title,
      session_type: values.session_type,
      part_type: values.part_type || null,
    });
    setOpenLabIds((current) => addId(current, createSessionTarget.lab.id));
    setOpenProjectIds((current) => addId(current, createSessionTarget.project.id));
    setCollapsedLabIds((current) => removeId(current, createSessionTarget.lab.id));
    setCollapsedProjectIds((current) => removeId(current, createSessionTarget.project.id));
    emitDataChanged();
    router.push(`/dashboard/sessions/${session.id}`);
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
          const isLabOpen = labIsOpen(lab.id);
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
                <Button
                  type="button"
                  size="icon-xs"
                  variant="ghost"
                  className="h-7 w-7 shrink-0 text-muted-foreground"
                  onClick={() => setCreateProjectLab(lab)}
                  aria-label={`Create project in ${lab.name}`}
                  title="Create project"
                >
                  <Plus className="h-3.5 w-3.5" />
                </Button>
              </div>

              {isLabOpen && (
                <div className="ml-3 space-y-1 border-l pl-3">
                  {lab.projects.map((project) => {
                    const isProjectOpen = projectIsOpen(project.id);
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
                          <Button
                            type="button"
                            size="icon-xs"
                            variant="ghost"
                            className="h-7 w-7 shrink-0 text-muted-foreground"
                            onClick={() => setCreateSessionTarget({ lab, project })}
                            aria-label={`Create session in ${project.name}`}
                            title="Create session"
                          >
                            <Plus className="h-3.5 w-3.5" />
                          </Button>
                        </div>

                        {isProjectOpen && (
                          <div className="ml-3 space-y-1 border-l pl-3">
                            {project.sessions.map((session) => (
                              <Link
                                key={session.id}
                                href={`/dashboard/sessions/${session.id}`}
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

      {createProjectLab && (
        <EntityFormDialog
          open={Boolean(createProjectLab)}
          onOpenChange={(open) => !open && setCreateProjectLab(null)}
          title="Create project"
          description={`A new project inside ${createProjectLab.name}.`}
          submitLabel="Create project"
          onSubmit={handleCreateProject}
          nameLabel="Project name"
          namePlaceholder="e.g. Bench tools"
        />
      )}

      {createSessionTarget && (
        <SessionFormDialog
          open={Boolean(createSessionTarget)}
          onOpenChange={(open) => !open && setCreateSessionTarget(null)}
          title="Create session"
          description={`A new session inside ${createSessionTarget.project.name}.`}
          submitLabel="Create session"
          showSessionType
          onSubmit={handleCreateSession}
        />
      )}
    </nav>
  );
}

function projectWorkspaceHref(labId: string, projectId?: string): string {
  const params = new URLSearchParams({ lab: labId });
  if (projectId) params.set("project", projectId);
  return `/dashboard/labs?${params.toString()}`;
}

function addId(current: Set<string>, id: string): Set<string> {
  const next = new Set(current);
  next.add(id);
  return next;
}

function removeId(current: Set<string>, id: string): Set<string> {
  const next = new Set(current);
  next.delete(id);
  return next;
}

function findSessionLocation(
  tree: LabNode[],
  sessionId: string | null,
): { labId: string; projectId: string } | null {
  if (!sessionId) return null;
  for (const lab of tree) {
    for (const project of lab.projects) {
      if (project.sessions.some((session) => session.id === sessionId)) {
        return { labId: lab.id, projectId: project.id };
      }
    }
  }
  return null;
}
