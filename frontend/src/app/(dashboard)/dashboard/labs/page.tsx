"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useAuth } from "@clerk/nextjs";
import {
  Archive,
  ChevronRight,
  FolderKanban,
  Pencil,
  Plus,
  Rows3,
  Settings,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { ConfirmDeleteDialog } from "@/components/dashboard/confirm-delete-dialog";
import { EntityFormDialog } from "@/components/dashboard/entity-form-dialog";
import { SessionFormDialog } from "@/components/dashboard/session-form-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  addLabMember,
  createProject,
  createSession,
  deleteLab,
  deleteProject,
  deleteSession,
  fetchCurrentUser,
  fetchLabMembers,
  fetchLabs,
  fetchProjects,
  fetchSessions,
  removeLabMember,
  updateLab,
  updateLabMember,
  updateProject,
  updateSession,
  type DesignSession,
  type Lab,
  type LabMembership,
  type LabRole,
  type Project,
  type SessionStatus,
  type UserProfile,
} from "@/lib/api";
import { emitDataChanged, useDataChangedListener } from "@/lib/data-events";

const GHOST_BUTTON_CLASS =
  "rounded-md border p-3 text-left transition-colors hover:bg-accent flex-1";
const INPUT_CLASS =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors focus:border-ring";
const SELECT_CLASS =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors focus:border-ring";

const ASSIGNABLE_ROLES: LabRole[] = ["admin", "member", "viewer"];

type SessionDialogMode =
  | { kind: "create" }
  | { kind: "edit"; session: DesignSession };

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

  const [user, setUser] = useState<UserProfile | null>(null);
  const [labs, setLabs] = useState<Lab[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [sessions, setSessions] = useState<DesignSession[]>([]);
  const [members, setMembers] = useState<LabMembership[]>([]);
  const [selectedLabId, setSelectedLabId] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [membersLoading, setMembersLoading] = useState(false);
  const [memberEmail, setMemberEmail] = useState("");
  const [memberRole, setMemberRole] = useState<LabRole>("viewer");
  const [memberActionError, setMemberActionError] = useState<string | null>(null);

  // Dialog state
  const [labSettingsOpen, setLabSettingsOpen] = useState(false);
  const [editLabOpen, setEditLabOpen] = useState(false);
  const [deleteLabOpen, setDeleteLabOpen] = useState(false);
  const [createProjectOpen, setCreateProjectOpen] = useState(false);
  const [editProject, setEditProject] = useState<Project | null>(null);
  const [deleteProjectTarget, setDeleteProjectTarget] = useState<Project | null>(null);
  const [sessionDialog, setSessionDialog] = useState<SessionDialogMode | null>(null);
  const [deleteSessionTarget, setDeleteSessionTarget] = useState<DesignSession | null>(null);
  const [removeMemberTarget, setRemoveMemberTarget] = useState<LabMembership | null>(null);

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

  const loadMembers = useCallback(async (token: string, labId: string | null) => {
    if (!labId) {
      setMembers([]);
      return;
    }

    setMembersLoading(true);
    setMemberActionError(null);
    try {
      setMembers(await fetchLabMembers(token, labId));
    } catch (err) {
      setMemberActionError(err instanceof Error ? err.message : "Failed to load members");
    } finally {
      setMembersLoading(false);
    }
  }, []);

  const loadWorkspace = useCallback(async () => {
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
        await Promise.all([
          loadProjects(token, nextLabId, projectParam, !labParam && !projectParam),
          loadMembers(token, nextLabId),
        ]);
      } else {
        setProjects([]);
        setSessions([]);
        setMembers([]);
        setSelectedProjectId(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load workspace");
    } finally {
      setLoading(false);
    }
  }, [getToken, labParam, loadMembers, loadProjects, projectParam]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- async data fetch
    loadWorkspace();
  }, [loadWorkspace]);

  useDataChangedListener(loadWorkspace);

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

  function handleSelectProject(projectId: string) {
    if (!selectedLab) return;
    router.push(projectWorkspaceHref(selectedLab.id, projectId));
  }

  async function withToken<T>(action: (token: string) => Promise<T>): Promise<T> {
    const token = await getToken();
    if (!token) {
      throw new Error("No Clerk session token. Sign out and sign back in.");
    }
    return action(token);
  }

  // Lab actions
  async function handleUpdateLab(values: { name: string; description: string }) {
    if (!selectedLab) return;
    await withToken((token) =>
      updateLab(token, selectedLab.id, {
        name: values.name,
        description: values.description || null,
      }),
    );
    emitDataChanged();
  }

  async function handleDeleteLab() {
    if (!selectedLab) return;
    await withToken((token) => deleteLab(token, selectedLab.id));
    emitDataChanged();
    router.push("/dashboard/labs");
  }

  // Member actions
  async function handleAddMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedLab || !memberEmail.trim()) return;

    setMemberActionError(null);
    try {
      await withToken((token) =>
        addLabMember(token, selectedLab.id, {
          email: memberEmail.trim(),
          role: memberRole,
        }),
      );
      setMemberEmail("");
      setMemberRole("viewer");
      emitDataChanged();
    } catch (err) {
      setMemberActionError(err instanceof Error ? err.message : "Failed to add member");
    }
  }

  async function handleChangeMemberRole(membership: LabMembership, role: LabRole) {
    if (!selectedLab || membership.role === role) return;

    setMemberActionError(null);
    try {
      await withToken((token) =>
        updateLabMember(token, selectedLab.id, membership.id, { role }),
      );
      emitDataChanged();
    } catch (err) {
      setMemberActionError(err instanceof Error ? err.message : "Failed to update role");
    }
  }

  async function handleRemoveMember() {
    if (!selectedLab || !removeMemberTarget) return;
    await withToken((token) => removeLabMember(token, selectedLab.id, removeMemberTarget.id));
    emitDataChanged();
  }

  // Project actions
  async function handleCreateProject(values: { name: string; description: string }) {
    if (!selectedLab) return;
    const project = await withToken((token) =>
      createProject(token, selectedLab.id, {
        name: values.name,
        description: values.description || null,
      }),
    );
    emitDataChanged();
    router.push(projectWorkspaceHref(selectedLab.id, project.id));
  }

  async function handleUpdateProject(values: { name: string; description: string }) {
    if (!editProject) return;
    await withToken((token) =>
      updateProject(token, editProject.id, {
        name: values.name,
        description: values.description || null,
      }),
    );
    emitDataChanged();
  }

  async function handleDeleteProject() {
    if (!deleteProjectTarget || !selectedLab) return;
    await withToken((token) => deleteProject(token, deleteProjectTarget.id));
    emitDataChanged();
    if (selectedProjectId === deleteProjectTarget.id) {
      router.push(projectWorkspaceHref(selectedLab.id));
    }
  }

  // Session actions
  async function handleSubmitSession(values: {
    title: string;
    part_type: string;
    status?: SessionStatus;
  }) {
    if (!sessionDialog) return;

    if (sessionDialog.kind === "create") {
      if (!selectedLab || !selectedProject) return;
      await withToken((token) =>
        createSession(token, selectedProject.id, {
          title: values.title,
          part_type: values.part_type || null,
        }),
      );
      emitDataChanged();
      router.push(projectWorkspaceHref(selectedLab.id, selectedProject.id));
    } else {
      const target = sessionDialog.session;
      await withToken((token) =>
        updateSession(token, target.id, {
          title: values.title,
          part_type: values.part_type || null,
          status: values.status,
        }),
      );
      emitDataChanged();
    }
  }

  async function handleArchiveSession(sessionToArchive: DesignSession) {
    await withToken((token) =>
      updateSession(token, sessionToArchive.id, { status: "archived" }),
    );
    emitDataChanged();
  }

  async function handleDeleteSession() {
    if (!deleteSessionTarget) return;
    await withToken((token) => deleteSession(token, deleteSessionTarget.id));
    emitDataChanged();
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
          <h1 className="text-2xl font-bold tracking-tight">
            {selectedProject
              ? selectedProject.name
              : selectedLab
                ? `${selectedLab.name} Projects`
                : "Projects"}
          </h1>
          <p className="text-muted-foreground">
            {selectedProject
              ? `Project workspace in ${selectedLab?.name}.`
              : selectedLab
                ? "Select or create a project to begin design work."
                : "Select a lab workspace from the sidebar."}
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

      <div className="grid gap-4">
        <section className="min-h-[520px] rounded-lg border bg-card">
          {selectedLab ? (
            <>
              <div className="flex flex-col gap-3 border-b p-5 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-1">
                  <p className="text-xs font-medium uppercase text-muted-foreground">
                    Lab workspace
                  </p>
                  <h2 className="text-xl font-semibold">
                    {selectedProject ? selectedProject.name : "Projects"}
                  </h2>
                  <p className="max-w-3xl text-sm text-muted-foreground">
                    {selectedProject
                      ? selectedProject.description || `Project in ${selectedLab.name}`
                      : selectedLab.description || `Workspace for ${selectedLab.name}`}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-muted px-3 py-1 text-xs font-medium">
                    {selectedLab.name}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setLabSettingsOpen(true)}
                    className="gap-1"
                  >
                    <Settings className="h-4 w-4" />
                    Lab settings
                  </Button>
                </div>
              </div>

              <div className="grid min-h-[420px] lg:grid-cols-[minmax(260px,0.45fr)_minmax(0,1fr)]">
                <div className="space-y-4 border-b p-5 lg:border-b-0 lg:border-r">
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1">
                      <h3 className="flex items-center gap-2 text-base font-semibold">
                        <FolderKanban className="h-4 w-4" />
                        Projects
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        Projects in {selectedLab.name}.
                      </p>
                    </div>
                    {canCreate(selectedLab) && (
                      <Button
                        size="sm"
                        onClick={() => setCreateProjectOpen(true)}
                        className="gap-1"
                      >
                        <Plus className="h-4 w-4" />
                        New
                      </Button>
                    )}
                  </div>

                  <div className="grid gap-2">
                    {projects.map((project) => (
                      <div
                        key={project.id}
                        className={`group flex items-stretch gap-1 ${
                          project.id === selectedProjectId ? "" : ""
                        }`}
                      >
                        <button
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
                        {canCreate(selectedLab) && (
                          <div className="flex flex-col gap-1">
                            <Button
                              size="icon"
                              variant="outline"
                              className="h-8 w-8"
                              onClick={() => setEditProject(project)}
                              title="Edit project"
                              aria-label="Edit project"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            {canDeleteProject(selectedLab) && (
                              <Button
                                size="icon"
                                variant="outline"
                                className="h-8 w-8 text-destructive hover:bg-destructive/10"
                                onClick={() => setDeleteProjectTarget(project)}
                                title="Delete project"
                                aria-label="Delete project"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                    {projects.length === 0 && (
                      <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                        No projects yet.
                      </p>
                    )}
                  </div>
                </div>

                <div className="space-y-4 p-5">
                  <div className="flex items-start justify-between gap-2">
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
                    {selectedProject && canCreate(selectedLab) && (
                      <Button
                        size="sm"
                        onClick={() => setSessionDialog({ kind: "create" })}
                        className="gap-1"
                      >
                        <Plus className="h-4 w-4" />
                        New
                      </Button>
                    )}
                  </div>

                  <div className="grid gap-2">
                    {sessions.map((sessionItem) => (
                      <div
                        key={sessionItem.id}
                        className={`group flex items-stretch gap-1`}
                      >
                        <div className="flex-1 rounded-md border p-3 text-left">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="font-medium">{sessionItem.title}</p>
                              <p className="text-xs text-muted-foreground">
                                {sessionItem.part_type || "No part type"}
                              </p>
                            </div>
                            <span className="rounded-full bg-muted px-2 py-1 text-xs font-medium">
                              {sessionItem.status}
                            </span>
                          </div>
                        </div>
                        {canCreate(selectedLab) && (
                          <div className="flex flex-col gap-1">
                            <Button
                              size="icon"
                              variant="outline"
                              className="h-8 w-8"
                              onClick={() =>
                                setSessionDialog({ kind: "edit", session: sessionItem })
                              }
                              title="Edit session"
                              aria-label="Edit session"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            {sessionItem.status !== "archived" && (
                              <Button
                                size="icon"
                                variant="outline"
                                className="h-8 w-8"
                                onClick={() => handleArchiveSession(sessionItem)}
                                title="Archive session"
                                aria-label="Archive session"
                              >
                                <Archive className="h-3.5 w-3.5" />
                              </Button>
                            )}
                            <Button
                              size="icon"
                              variant="outline"
                              className="h-8 w-8 text-destructive hover:bg-destructive/10"
                              onClick={() => setDeleteSessionTarget(sessionItem)}
                              title="Delete session"
                              aria-label="Delete session"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        )}
                      </div>
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
                  Pick a lab from the sidebar, or click + in the sidebar to create one.
                </p>
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Lab settings dialog */}
      {selectedLab && (
        <Dialog open={labSettingsOpen} onOpenChange={setLabSettingsOpen}>
          <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-4xl">
            <DialogHeader>
              <DialogTitle>Lab settings</DialogTitle>
              <DialogDescription>
                Manage workspace details, member roles, and lab-level access.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-6">
              <section className="rounded-md border p-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div className="space-y-1">
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Workspace
                    </p>
                    <h3 className="text-base font-semibold">{selectedLab.name}</h3>
                    <p className="max-w-2xl text-sm text-muted-foreground">
                      {selectedLab.description || "No description"}
                    </p>
                    <span className="inline-flex rounded-full bg-muted px-2 py-1 text-xs font-medium">
                      Your role: {roleDetails(selectedLab.role).label}
                    </span>
                  </div>

                  {canManageLab(selectedLab) && (
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setEditLabOpen(true)}
                        className="gap-1"
                      >
                        <Pencil className="h-4 w-4" />
                        Edit
                      </Button>
                      {selectedLab.role === "owner" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setDeleteLabOpen(true)}
                          className="gap-1 text-destructive hover:bg-destructive/10"
                        >
                          <Trash2 className="h-4 w-4" />
                          Delete
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              </section>

              <section className="space-y-4 rounded-md border p-4">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                  <div className="space-y-1">
                    <h3 className="flex items-center gap-2 text-base font-semibold">
                      <Users className="h-4 w-4" />
                      Members and roles
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Admin: PI/Post-Docs. Supervisor: senior lab members. User: visiting
                      researchers and general lab members.
                    </p>
                  </div>

                  {canManageMembers(selectedLab) && (
                    <form
                      className="grid gap-2 md:grid-cols-[minmax(220px,1fr)_180px_auto]"
                      onSubmit={handleAddMember}
                    >
                      <input
                        className={INPUT_CLASS}
                        value={memberEmail}
                        onChange={(event) => setMemberEmail(event.target.value)}
                        placeholder="member@example.com"
                        type="email"
                      />
                      <select
                        className={SELECT_CLASS}
                        value={memberRole}
                        onChange={(event) => setMemberRole(event.target.value as LabRole)}
                      >
                        {ASSIGNABLE_ROLES.map((role) => (
                          <option key={role} value={role}>
                            {roleOptionLabel(role)}
                          </option>
                        ))}
                      </select>
                      <Button type="submit" disabled={!memberEmail.trim()} className="gap-1">
                        <UserPlus className="h-4 w-4" />
                        Add
                      </Button>
                    </form>
                  )}
                </div>

                {memberActionError && (
                  <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    {memberActionError}
                  </p>
                )}

                <div className="grid gap-2">
                  {membersLoading && (
                    <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                      Loading members...
                    </p>
                  )}

                  {!membersLoading &&
                    members.map((member) => {
                      const details = roleDetails(member.role);
                      return (
                        <div
                          key={member.id}
                          className="grid gap-3 rounded-md border p-3 md:grid-cols-[minmax(0,1fr)_220px_auto] md:items-center"
                        >
                          <div className="flex min-w-0 items-center gap-3">
                            <Avatar className="h-8 w-8">
                              <AvatarImage src={member.avatar_url || undefined} />
                              <AvatarFallback>{initialsForMember(member)}</AvatarFallback>
                            </Avatar>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium">
                                {member.display_name || member.email}
                              </p>
                              <p className="truncate text-xs text-muted-foreground">
                                {member.email}
                              </p>
                            </div>
                          </div>

                          {canManageMembers(selectedLab) ? (
                            <select
                              className={SELECT_CLASS}
                              value={member.role}
                              onChange={(event) =>
                                handleChangeMemberRole(member, event.target.value as LabRole)
                              }
                            >
                              {roleOptionsFor(member.role).map((role) => (
                                <option key={role} value={role}>
                                  {roleOptionLabel(role)}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <div>
                              <span className="rounded-full bg-muted px-2 py-1 text-xs font-medium">
                                {details.label}
                              </span>
                              <p className="mt-1 text-xs text-muted-foreground">
                                {details.description}
                              </p>
                            </div>
                          )}

                          {canManageMembers(selectedLab) && (
                            <Button
                              size="icon-sm"
                              variant="outline"
                              className="text-destructive hover:bg-destructive/10"
                              onClick={() => setRemoveMemberTarget(member)}
                              title="Remove member"
                              aria-label="Remove member"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      );
                    })}

                  {!membersLoading && members.length === 0 && (
                    <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                      No members found.
                    </p>
                  )}
                </div>
              </section>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Lab edit dialog */}
      {selectedLab && (
        <EntityFormDialog
          open={editLabOpen}
          onOpenChange={setEditLabOpen}
          title="Edit laboratory"
          submitLabel="Save changes"
          initialValues={{ name: selectedLab.name, description: selectedLab.description ?? "" }}
          onSubmit={handleUpdateLab}
          nameLabel="Lab name"
        />
      )}

      {/* Lab delete dialog */}
      {selectedLab && (
        <ConfirmDeleteDialog
          open={deleteLabOpen}
          onOpenChange={setDeleteLabOpen}
          title={`Delete ${selectedLab.name}?`}
          description="This will permanently delete the lab, all of its projects, sessions, and artifacts. This cannot be undone."
          onConfirm={handleDeleteLab}
        />
      )}

      {/* Project create dialog */}
      {selectedLab && (
        <EntityFormDialog
          open={createProjectOpen}
          onOpenChange={setCreateProjectOpen}
          title="Create project"
          description={`A new project inside ${selectedLab.name}.`}
          submitLabel="Create project"
          onSubmit={handleCreateProject}
          nameLabel="Project name"
          namePlaceholder="e.g. Bench tools"
        />
      )}

      {/* Project edit dialog */}
      {editProject && (
        <EntityFormDialog
          open={Boolean(editProject)}
          onOpenChange={(open) => !open && setEditProject(null)}
          title="Edit project"
          submitLabel="Save changes"
          initialValues={{ name: editProject.name, description: editProject.description ?? "" }}
          onSubmit={handleUpdateProject}
          nameLabel="Project name"
        />
      )}

      {/* Project delete dialog */}
      {deleteProjectTarget && (
        <ConfirmDeleteDialog
          open={Boolean(deleteProjectTarget)}
          onOpenChange={(open) => !open && setDeleteProjectTarget(null)}
          title={`Delete ${deleteProjectTarget.name}?`}
          description="This will permanently delete the project and all of its sessions and artifacts."
          onConfirm={handleDeleteProject}
        />
      )}

      {/* Session create/edit dialog */}
      {sessionDialog && (
        <SessionFormDialog
          open={Boolean(sessionDialog)}
          onOpenChange={(open) => !open && setSessionDialog(null)}
          title={sessionDialog.kind === "create" ? "Create design session" : "Edit session"}
          submitLabel={sessionDialog.kind === "create" ? "Create session" : "Save changes"}
          initialValues={
            sessionDialog.kind === "edit"
              ? {
                  title: sessionDialog.session.title,
                  part_type: sessionDialog.session.part_type ?? "",
                  status: sessionDialog.session.status,
                }
              : undefined
          }
          showStatus={sessionDialog.kind === "edit"}
          onSubmit={handleSubmitSession}
        />
      )}

      {/* Session delete dialog */}
      {deleteSessionTarget && (
        <ConfirmDeleteDialog
          open={Boolean(deleteSessionTarget)}
          onOpenChange={(open) => !open && setDeleteSessionTarget(null)}
          title={`Delete ${deleteSessionTarget.title}?`}
          description="This will permanently delete the session and all of its messages and artifacts."
          onConfirm={handleDeleteSession}
        />
      )}

      {/* Member remove dialog */}
      {removeMemberTarget && (
        <ConfirmDeleteDialog
          open={Boolean(removeMemberTarget)}
          onOpenChange={(open) => !open && setRemoveMemberTarget(null)}
          title={`Remove ${removeMemberTarget.display_name || removeMemberTarget.email}?`}
          description="This removes the user's access to this lab and its projects and sessions."
          confirmLabel="Remove"
          onConfirm={handleRemoveMember}
        />
      )}
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

function initialsForMember(member: LabMembership): string {
  return (member.display_name || member.email)
    .split(" ")
    .map((part) => part[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function projectWorkspaceHref(labId: string, projectId?: string): string {
  const params = new URLSearchParams({ lab: labId });
  if (projectId) params.set("project", projectId);
  return `/dashboard/labs?${params.toString()}`;
}

function canManageLab(lab: Lab): boolean {
  return lab.role === "owner" || lab.role === "admin";
}

function canManageMembers(lab: Lab): boolean {
  return lab.role === "owner" || lab.role === "admin";
}

function canCreate(lab: Lab): boolean {
  return lab.role === "owner" || lab.role === "admin" || lab.role === "member";
}

function canDeleteProject(lab: Lab): boolean {
  return lab.role === "owner" || lab.role === "admin";
}

function roleOptionsFor(currentRole: LabRole): LabRole[] {
  if (currentRole === "owner") {
    return ["owner", ...ASSIGNABLE_ROLES];
  }
  return ASSIGNABLE_ROLES;
}

function roleDetails(role: LabRole | null): { label: string; description: string } {
  switch (role) {
    case "owner":
      return {
        label: "Admin",
        description: "PI/Post-Doc with lab ownership protection.",
      };
    case "admin":
      return {
        label: "Admin",
        description: "PI/Post-Doc with lab and member management access.",
      };
    case "member":
      return {
        label: "Supervisor",
        description: "Senior lab member who can manage projects and sessions.",
      };
    case "viewer":
      return {
        label: "User",
        description: "Visiting researcher or general lab member.",
      };
    default:
      return {
        label: "No role",
        description: "No lab access role is assigned.",
      };
  }
}

function roleOptionLabel(role: LabRole): string {
  return role === "owner" ? "Admin (owner)" : roleDetails(role).label;
}
