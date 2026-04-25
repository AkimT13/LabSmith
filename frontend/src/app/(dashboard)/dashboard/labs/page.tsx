"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useAuth } from "@clerk/nextjs";
import { ChevronRight, FolderKanban, FlaskConical, Plus, Rows3 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  createLab,
  createProject,
  createSession,
  fetchCurrentUser,
  fetchLabs,
  fetchProjects,
  fetchSessions,
  type DesignSession,
  type Lab,
  type Project,
  type UserProfile,
} from "@/lib/api";

const INPUT_CLASS =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors focus:border-ring";
const TEXTAREA_CLASS =
  "min-h-20 w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-ring";
const BUTTON_CLASS =
  "inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50";
const GHOST_BUTTON_CLASS =
  "rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-accent";

export default function LabsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-12">
          <p className="text-muted-foreground">Loading...</p>
        </div>
      }
    >
      <LabsWorkspace />
    </Suspense>
  );
}

function LabsWorkspace() {
  const { getToken } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const labParam = searchParams.get("lab");
  const projectParam = searchParams.get("project");
  const selectedSessionId = searchParams.get("session");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [labs, setLabs] = useState<Lab[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [sessions, setSessions] = useState<DesignSession[]>([]);
  const [selectedLabId, setSelectedLabId] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [labName, setLabName] = useState("");
  const [labDescription, setLabDescription] = useState("");
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [sessionTitle, setSessionTitle] = useState("");
  const [sessionPartType, setSessionPartType] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const selectedLab = useMemo(
    () => labs.find((lab) => lab.id === selectedLabId) ?? null,
    [labs, selectedLabId],
  );
  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  const loadProjects = useCallback(
    async (
      token: string,
      labId: string,
      preferredProjectId: string | null = null,
      selectFirstProject = true,
    ) => {
      const loadedProjects = await fetchProjects(token, labId);
      setProjects(loadedProjects);
      setSelectedProjectId((currentId) => {
        if (
          preferredProjectId &&
          loadedProjects.some((project) => project.id === preferredProjectId)
        ) {
          return preferredProjectId;
        }
        if (!preferredProjectId && !selectFirstProject) {
          return null;
        }
        if (currentId && loadedProjects.some((project) => project.id === currentId)) {
          return currentId;
        }
        return selectFirstProject ? (loadedProjects[0]?.id ?? null) : null;
      });
    },
    [],
  );

  const loadSessions = useCallback(async (token: string, projectId: string | null) => {
    if (!projectId) {
      setSessions([]);
      return;
    }
    setSessions(await fetchSessions(token, projectId));
  }, []);

  useEffect(() => {
    async function loadWorkspace() {
      setLoading(true);
      setError(null);

      try {
        const token = await getToken();
        if (!token) {
          setError("No Clerk session token was available. Sign out and sign back in.");
          setLoading(false);
          return;
        }

        const [profile, loadedLabs] = await Promise.all([
          fetchCurrentUser(token),
          fetchLabs(token),
        ]);
        setUser(profile);
        setLabs(loadedLabs);

        const selectedFromUrl = labParam
          ? loadedLabs.find((lab) => lab.id === labParam)
          : null;
        const nextLabId = selectedFromUrl?.id ?? loadedLabs[0]?.id ?? null;
        setSelectedLabId(nextLabId);
        if (nextLabId) {
          await loadProjects(token, nextLabId, projectParam, !labParam && !projectParam);
        } else {
          setProjects([]);
          setSessions([]);
          setSelectedProjectId(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load workspace");
      } finally {
        setLoading(false);
      }
    }

    loadWorkspace();
  }, [getToken, labParam, loadProjects, projectParam]);

  useEffect(() => {
    async function refreshSessions() {
      try {
        const token = await getToken();
        if (!token) return;
        await loadSessions(token, selectedProjectId);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load sessions");
      }
    }

    refreshSessions();
  }, [getToken, loadSessions, selectedProjectId]);

  async function handleSelectLab(labId: string) {
    router.push(workspaceHref(labId));
    setSelectedLabId(labId);
    setSelectedProjectId(null);
    setProjects([]);
    setSessions([]);
    setError(null);

    const token = await getToken();
    if (!token) return;
    try {
      await loadProjects(token, labId, null, false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    }
  }

  function handleSelectProject(projectId: string) {
    if (!selectedLab) return;
    router.push(workspaceHref(selectedLab.id, projectId));
    setSelectedProjectId(projectId);
    setSessions([]);
  }

  function handleSelectSession(sessionId: string) {
    if (!selectedLab || !selectedProject) return;
    router.push(workspaceHref(selectedLab.id, selectedProject.id, sessionId));
  }

  async function handleCreateLab(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!labName.trim()) return;

    await runSavingAction(async (token) => {
      const lab = await createLab(token, {
        name: labName.trim(),
        description: labDescription.trim() || null,
      });
      setLabs((currentLabs) => [lab, ...currentLabs]);
      setSelectedLabId(lab.id);
      setProjects([]);
      setSessions([]);
      setSelectedProjectId(null);
      setLabName("");
      setLabDescription("");
      router.push(workspaceHref(lab.id));
    });
  }

  async function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedLab || !projectName.trim()) return;

    await runSavingAction(async (token) => {
      const project = await createProject(token, selectedLab.id, {
        name: projectName.trim(),
        description: projectDescription.trim() || null,
      });
      setProjects((currentProjects) => [project, ...currentProjects]);
      setSelectedProjectId(project.id);
      setSessions([]);
      setProjectName("");
      setProjectDescription("");
      router.push(workspaceHref(selectedLab.id, project.id));
    });
  }

  async function handleCreateSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedLab || !selectedProject || !sessionTitle.trim()) return;

    await runSavingAction(async (token) => {
      const designSession = await createSession(token, selectedProject.id, {
        title: sessionTitle.trim(),
        part_type: sessionPartType.trim() || null,
      });
      setSessions((currentSessions) => [designSession, ...currentSessions]);
      setSessionTitle("");
      setSessionPartType("");
      router.push(workspaceHref(selectedLab.id, selectedProject.id, designSession.id));
    });
  }

  async function runSavingAction(action: (token: string) => Promise<void>) {
    setSaving(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) {
        setError("No Clerk session token was available. Sign out and sign back in.");
        return;
      }
      await action(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Laboratories</h1>
          <p className="text-muted-foreground">
            Select a lab, then work through its projects and design sessions.
          </p>
        </div>

        {user && (
          <div className="flex items-center gap-3 rounded-md border px-3 py-2">
            <Avatar className="h-9 w-9">
              <AvatarImage src={user.avatar_url || undefined} />
              <AvatarFallback>{initialsFor(user)}</AvatarFallback>
            </Avatar>
            <div>
              <p className="text-sm font-medium">{user.display_name || "No name set"}</p>
              <p className="text-xs text-muted-foreground">{user.email}</p>
            </div>
          </div>
        )}
      </header>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/20 px-3 py-2 text-sm">
        <span className="font-medium">Labs</span>
        {selectedLab && (
          <>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">{selectedLab.name}</span>
          </>
        )}
        {selectedProject && (
          <>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">{selectedProject.name}</span>
          </>
        )}
      </div>

      <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
        <section className="rounded-lg border bg-card">
          <div className="border-b p-5">
            <div className="space-y-1">
              <h2 className="flex items-center gap-2 text-base font-semibold">
                <FlaskConical className="h-4 w-4" />
                Labs
              </h2>
              <p className="text-sm text-muted-foreground">Top-level workspaces.</p>
            </div>
          </div>
          <div className="space-y-4 p-5">
            <form className="space-y-3" onSubmit={handleCreateLab}>
              <input
                className={INPUT_CLASS}
                value={labName}
                onChange={(event) => setLabName(event.target.value)}
                placeholder="Lab name"
              />
              <textarea
                className={TEXTAREA_CLASS}
                value={labDescription}
                onChange={(event) => setLabDescription(event.target.value)}
                placeholder="Description"
              />
              <button className={BUTTON_CLASS} type="submit" disabled={saving || !labName.trim()}>
                <Plus className="h-4 w-4" />
                Create lab
              </button>
            </form>

            <div className="grid gap-2">
              {labs.map((lab) => (
                <button
                  key={lab.id}
                  className={`${GHOST_BUTTON_CLASS} ${
                    lab.id === selectedLabId ? "border-primary bg-accent" : ""
                  }`}
                  type="button"
                  onClick={() => handleSelectLab(lab.id)}
                >
                  <span className="block font-medium">{lab.name}</span>
                  <span className="text-xs text-muted-foreground">{lab.role}</span>
                </button>
              ))}
              {labs.length === 0 && (
                <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                  No labs yet.
                </p>
              )}
            </div>
          </div>
        </section>

        <section className="min-h-[520px] rounded-lg border bg-card">
          {selectedLab ? (
            <>
              <div className="flex flex-col gap-3 border-b p-5 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-1">
                  <p className="text-xs font-medium uppercase text-muted-foreground">
                    Selected lab
                  </p>
                  <h2 className="text-xl font-semibold">{selectedLab.name}</h2>
                  <p className="max-w-3xl text-sm text-muted-foreground">
                    {selectedLab.description || "No description"}
                  </p>
                </div>
                <span className="w-fit rounded-full bg-muted px-3 py-1 text-xs font-medium">
                  {selectedLab.role}
                </span>
              </div>

              <div className="grid min-h-[420px] lg:grid-cols-[minmax(260px,0.45fr)_minmax(0,1fr)]">
                <div className="space-y-4 border-b p-5 lg:border-b-0 lg:border-r">
                  <div className="space-y-1">
                    <h3 className="flex items-center gap-2 text-base font-semibold">
                      <FolderKanban className="h-4 w-4" />
                      Projects
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Projects in {selectedLab.name}.
                    </p>
                  </div>

                  <form className="space-y-3" onSubmit={handleCreateProject}>
                    <input
                      className={INPUT_CLASS}
                      value={projectName}
                      onChange={(event) => setProjectName(event.target.value)}
                      placeholder="Project name"
                    />
                    <textarea
                      className={TEXTAREA_CLASS}
                      value={projectDescription}
                      onChange={(event) => setProjectDescription(event.target.value)}
                      placeholder="Description"
                    />
                    <button
                      className={BUTTON_CLASS}
                      type="submit"
                      disabled={saving || !projectName.trim()}
                    >
                      <Plus className="h-4 w-4" />
                      Create project
                    </button>
                  </form>

                  <div className="grid gap-2">
                    {projects.map((project) => (
                      <button
                        key={project.id}
                        className={`${GHOST_BUTTON_CLASS} ${
                          project.id === selectedProjectId ? "border-primary bg-accent" : ""
                        }`}
                        type="button"
                        onClick={() => handleSelectProject(project.id)}
                      >
                        <span className="block font-medium">{project.name}</span>
                        <span className="text-xs text-muted-foreground">
                          {project.description || "No description"}
                        </span>
                      </button>
                    ))}
                    {projects.length === 0 && (
                      <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                        No projects yet.
                      </p>
                    )}
                  </div>
                </div>

                <div className="space-y-4 p-5">
                  <div className="space-y-1">
                    <h3 className="flex items-center gap-2 text-base font-semibold">
                      <Rows3 className="h-4 w-4" />
                      {selectedProject ? `Sessions in ${selectedProject.name}` : "Sessions"}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {selectedProject
                        ? `Design sessions for ${selectedProject.name}.`
                        : "Select a project to manage sessions."}
                    </p>
                  </div>

                  <form className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px_auto]" onSubmit={handleCreateSession}>
                    <input
                      className={INPUT_CLASS}
                      value={sessionTitle}
                      onChange={(event) => setSessionTitle(event.target.value)}
                      placeholder="Session title"
                      disabled={!selectedProject}
                    />
                    <input
                      className={INPUT_CLASS}
                      value={sessionPartType}
                      onChange={(event) => setSessionPartType(event.target.value)}
                      placeholder="Part type"
                      disabled={!selectedProject}
                    />
                    <button
                      className={BUTTON_CLASS}
                      type="submit"
                      disabled={saving || !selectedProject || !sessionTitle.trim()}
                    >
                      <Plus className="h-4 w-4" />
                      Create
                    </button>
                  </form>

                  <div className="grid gap-2">
                    {sessions.map((session) => (
                      <button
                        key={session.id}
                        className={`rounded-md border p-3 text-left transition-colors hover:bg-accent ${
                          session.id === selectedSessionId ? "border-primary bg-accent" : ""
                        }`}
                        type="button"
                        onClick={() => handleSelectSession(session.id)}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-medium">{session.title}</p>
                            <p className="text-xs text-muted-foreground">
                              {session.part_type || "No part type"}
                            </p>
                          </div>
                          <span className="rounded-full bg-muted px-2 py-1 text-xs font-medium">
                            {session.status}
                          </span>
                        </div>
                      </button>
                    ))}
                    {selectedProject && sessions.length === 0 && (
                      <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                        No sessions yet.
                      </p>
                    )}
                    {!selectedProject && (
                      <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                        Select or create a project to manage sessions.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="flex min-h-[520px] items-center justify-center p-6 text-center">
              <div className="max-w-sm space-y-2">
                <h2 className="text-lg font-semibold">Select a lab</h2>
                <p className="text-sm text-muted-foreground">
                  Create or select a lab to view its projects and sessions.
                </p>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function initialsFor(user: UserProfile): string {
  return (user.display_name || user.email)
    .split(" ")
    .map((part) => part[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function workspaceHref(labId: string, projectId?: string, sessionId?: string): string {
  const params = new URLSearchParams({ lab: labId });
  if (projectId) params.set("project", projectId);
  if (sessionId) params.set("session", sessionId);
  return `/dashboard/labs?${params.toString()}`;
}
