"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useAuth } from "@clerk/nextjs";
import { FolderKanban, FlaskConical, Plus, Rows3 } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  const { getToken } = useAuth();
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
    async (token: string, labId: string) => {
      const loadedProjects = await fetchProjects(token, labId);
      setProjects(loadedProjects);
      setSelectedProjectId((currentId) => {
        if (currentId && loadedProjects.some((project) => project.id === currentId)) {
          return currentId;
        }
        return loadedProjects[0]?.id ?? null;
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

        const firstLabId = loadedLabs[0]?.id ?? null;
        setSelectedLabId(firstLabId);
        if (firstLabId) {
          await loadProjects(token, firstLabId);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load workspace");
      } finally {
        setLoading(false);
      }
    }

    loadWorkspace();
  }, [getToken, loadProjects]);

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
    setSelectedLabId(labId);
    setSelectedProjectId(null);
    setProjects([]);
    setSessions([]);
    setError(null);

    const token = await getToken();
    if (!token) return;
    try {
      await loadProjects(token, labId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    }
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
    });
  }

  async function handleCreateSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProject || !sessionTitle.trim()) return;

    await runSavingAction(async (token) => {
      const designSession = await createSession(token, selectedProject.id, {
        title: sessionTitle.trim(),
        part_type: sessionPartType.trim() || null,
      });
      setSessions((currentSessions) => [designSession, ...currentSessions]);
      setSessionTitle("");
      setSessionPartType("");
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
          <p className="text-muted-foreground">Labs, projects, and design sessions.</p>
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

      <div className="grid gap-4 xl:grid-cols-[minmax(260px,0.8fr)_minmax(320px,1fr)_minmax(320px,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FlaskConical className="h-4 w-4" />
              Labs
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FolderKanban className="h-4 w-4" />
              Projects
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <form className="space-y-3" onSubmit={handleCreateProject}>
              <input
                className={INPUT_CLASS}
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
                placeholder="Project name"
                disabled={!selectedLab}
              />
              <textarea
                className={TEXTAREA_CLASS}
                value={projectDescription}
                onChange={(event) => setProjectDescription(event.target.value)}
                placeholder="Description"
                disabled={!selectedLab}
              />
              <button
                className={BUTTON_CLASS}
                type="submit"
                disabled={saving || !selectedLab || !projectName.trim()}
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
                  onClick={() => setSelectedProjectId(project.id)}
                >
                  <span className="block font-medium">{project.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {project.description || "No description"}
                  </span>
                </button>
              ))}
              {selectedLab && projects.length === 0 && (
                <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                  No projects yet.
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Rows3 className="h-4 w-4" />
              Sessions
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <form className="space-y-3" onSubmit={handleCreateSession}>
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
                Create session
              </button>
            </form>

            <div className="grid gap-2">
              {sessions.map((session) => (
                <div key={session.id} className="rounded-md border p-3">
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
                </div>
              ))}
              {selectedProject && sessions.length === 0 && (
                <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                  No sessions yet.
                </p>
              )}
            </div>
          </CardContent>
        </Card>
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
