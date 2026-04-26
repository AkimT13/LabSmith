const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
const API_BASE_URL = configuredApiBaseUrl || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const { token, ...fetchOptions } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOptions.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(buildApiUrl(path), {
    ...fetchOptions,
    headers,
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export function buildApiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path;
  }

  if (!/^https?:\/\//.test(API_BASE_URL)) {
    throw new ApiError(
      0,
      `Invalid NEXT_PUBLIC_API_BASE_URL: "${API_BASE_URL}". Expected a full http:// or https:// URL.`,
    );
  }

  const baseUrl = API_BASE_URL.replace(/\/$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${baseUrl}${normalizedPath}`;
}

async function readErrorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    const body = (await response.json()) as { detail?: unknown; message?: unknown };
    const detail = body.detail ?? body.message;
    return typeof detail === "string" ? detail : `API request failed with ${response.status}`;
  }

  const text = await response.text();
  if (/^\s*<!doctype html/i.test(text) || /^\s*<html/i.test(text)) {
    return (
      `API request returned HTML with status ${response.status}. ` +
      "Check that NEXT_PUBLIC_API_BASE_URL points to the FastAPI backend."
    );
  }

  return text || `API request failed with ${response.status}`;
}

// Types
export interface UserProfile {
  id: string;
  clerk_user_id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
}

export type LabRole = "owner" | "admin" | "member" | "viewer";
export type SessionStatus = "active" | "completed" | "archived";
export type SessionType = "part_design" | "onboarding";
export type MessageRole = "user" | "assistant" | "system";
export type ArtifactType = "stl" | "step" | "spec_json" | "validation_json";
export type PartType =
  | "tube_rack"
  | "gel_comb"
  | "pipette_tip_rack"
  | "petri_dish_stand"
  | "microfluidic_channel_mold";

export interface Lab {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  role: LabRole | null;
}

export interface LabMembership {
  id: string;
  laboratory_id: string;
  user_id: string;
  role: LabRole;
  invited_by: string | null;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  laboratory_id: string;
  name: string;
  description: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface DesignSession {
  id: string;
  project_id: string;
  title: string;
  status: SessionStatus;
  session_type: SessionType;
  part_type: string | null;
  current_spec: PartRequest | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface PartRequest {
  part_type: PartType;
  source_prompt: string | null;
  rows: number | null;
  cols: number | null;
  well_count: number | null;
  diameter_mm: number | null;
  spacing_mm: number | null;
  depth_mm: number | null;
  well_width_mm: number | null;
  well_height_mm: number | null;
  tube_volume_ml: number | null;
  max_width_mm: number | null;
  max_depth_mm: number | null;
  max_height_mm: number | null;
  notes: string[];
}

export interface ValidationIssue {
  severity: "error" | "warning";
  code: string;
  message: string;
  field: string | null;
}

export interface PrintabilityCheck {
  code: string;
  status: "pass" | "warning" | "error" | "unknown";
  message: string;
}

export interface PrintabilityReport {
  dimensions_mm: {
    width: number;
    depth: number;
    height: number;
  };
  bed_mm: {
    width: number;
    depth: number;
    height: number;
  };
  material_estimate: {
    volume_cm3: number;
    mass_g: number;
    method: string;
  };
  checks: PrintabilityCheck[];
}

export interface ArtifactValidation {
  issues?: ValidationIssue[];
  printability?: PrintabilityReport;
}

export interface Message {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface Artifact {
  id: string;
  session_id: string;
  message_id: string | null;
  artifact_type: ArtifactType;
  file_path: string | null;
  file_size_bytes: number | null;
  spec_snapshot: Record<string, unknown> | null;
  validation: ArtifactValidation | null;
  version: number;
  created_at: string;
  download_url: string | null;
  preview_url: string | null;
}

export interface LabDocument {
  id: string;
  laboratory_id: string;
  title: string;
  source_filename: string | null;
  content_type: string;
  file_size_bytes: number;
  uploaded_by: string;
  created_at: string;
  download_url: string;
}

// API calls
export function fetchCurrentUser(token: string): Promise<UserProfile> {
  return apiFetch<UserProfile>("/api/v1/auth/me", { token });
}

export function fetchLabs(token: string): Promise<Lab[]> {
  return apiFetch<Lab[]>("/api/v1/labs", { token });
}

export function fetchLab(token: string, labId: string): Promise<Lab> {
  return apiFetch<Lab>(`/api/v1/labs/${labId}`, { token });
}

export function createLab(
  token: string,
  data: { name: string; description?: string | null },
): Promise<Lab> {
  return apiFetch<Lab>("/api/v1/labs", {
    method: "POST",
    token,
    body: JSON.stringify(data),
  });
}

export function fetchProjects(token: string, labId: string): Promise<Project[]> {
  return apiFetch<Project[]>(`/api/v1/labs/${labId}/projects`, { token });
}

export function fetchProject(token: string, projectId: string): Promise<Project> {
  return apiFetch<Project>(`/api/v1/projects/${projectId}`, { token });
}

export function createProject(
  token: string,
  labId: string,
  data: { name: string; description?: string | null },
): Promise<Project> {
  return apiFetch<Project>(`/api/v1/labs/${labId}/projects`, {
    method: "POST",
    token,
    body: JSON.stringify(data),
  });
}

export function fetchSessions(token: string, projectId: string): Promise<DesignSession[]> {
  return apiFetch<DesignSession[]>(`/api/v1/projects/${projectId}/sessions`, { token });
}

export function fetchSession(token: string, sessionId: string): Promise<DesignSession> {
  return apiFetch<DesignSession>(`/api/v1/sessions/${sessionId}`, { token });
}

export function fetchMessages(token: string, sessionId: string): Promise<Message[]> {
  return apiFetch<Message[]>(`/api/v1/sessions/${sessionId}/messages`, { token });
}

export function fetchArtifacts(token: string, sessionId: string): Promise<Artifact[]> {
  return apiFetch<Artifact[]>(`/api/v1/sessions/${sessionId}/artifacts`, { token });
}

export async function fetchArtifactResponse(
  token: string,
  url: string,
  options: { ifNoneMatch?: string; signal?: AbortSignal } = {},
): Promise<Response> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };

  if (options.ifNoneMatch) {
    headers["If-None-Match"] = options.ifNoneMatch;
  }

  const response = await fetch(buildApiUrl(url), {
    headers,
    signal: options.signal,
  });

  if (!response.ok && response.status !== 304) {
    throw new ApiError(response.status, await readErrorMessage(response));
  }

  return response;
}

export async function postChat(
  token: string,
  sessionId: string,
  data: { content: string; metadata?: Record<string, unknown> },
  signal?: AbortSignal,
): Promise<Response> {
  const response = await fetch(buildApiUrl(`/api/v1/sessions/${sessionId}/chat`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
    signal,
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response));
  }

  return response;
}

export function createSession(
  token: string,
  projectId: string,
  data: {
    title: string;
    session_type?: SessionType;
    part_type?: string | null;
    current_spec?: Record<string, unknown> | null;
  },
): Promise<DesignSession> {
  return apiFetch<DesignSession>(`/api/v1/projects/${projectId}/sessions`, {
    method: "POST",
    token,
    body: JSON.stringify(data),
  });
}

// Updates / deletes
export function updateLab(
  token: string,
  labId: string,
  data: { name?: string; description?: string | null },
): Promise<Lab> {
  return apiFetch<Lab>(`/api/v1/labs/${labId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(data),
  });
}

export function deleteLab(token: string, labId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/labs/${labId}`, {
    method: "DELETE",
    token,
  });
}

export function fetchLabMembers(token: string, labId: string): Promise<LabMembership[]> {
  return apiFetch<LabMembership[]>(`/api/v1/labs/${labId}/members`, { token });
}

export function addLabMember(
  token: string,
  labId: string,
  data: { email: string; role: LabRole },
): Promise<LabMembership> {
  return apiFetch<LabMembership>(`/api/v1/labs/${labId}/members`, {
    method: "POST",
    token,
    body: JSON.stringify(data),
  });
}

export function updateLabMember(
  token: string,
  labId: string,
  membershipId: string,
  data: { role: LabRole },
): Promise<LabMembership> {
  return apiFetch<LabMembership>(`/api/v1/labs/${labId}/members/${membershipId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(data),
  });
}

export function removeLabMember(
  token: string,
  labId: string,
  membershipId: string,
): Promise<void> {
  return apiFetch<void>(`/api/v1/labs/${labId}/members/${membershipId}`, {
    method: "DELETE",
    token,
  });
}

// ---------------------------------------------------------------------------
// Lab documents (M9)
// ---------------------------------------------------------------------------

export function fetchLabDocuments(
  token: string,
  labId: string,
): Promise<LabDocument[]> {
  return apiFetch<LabDocument[]>(`/api/v1/labs/${labId}/documents`, { token });
}

export function createLabDocument(
  token: string,
  labId: string,
  data: {
    title: string;
    content: string;
    source_filename?: string | null;
    content_type?: string;
  },
): Promise<LabDocument> {
  return apiFetch<LabDocument>(`/api/v1/labs/${labId}/documents`, {
    method: "POST",
    token,
    body: JSON.stringify({
      title: data.title,
      content: data.content,
      source_filename: data.source_filename ?? null,
      content_type: data.content_type ?? "text/plain",
    }),
  });
}

export function deleteLabDocument(token: string, documentId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/documents/${documentId}`, {
    method: "DELETE",
    token,
  });
}

/**
 * Trigger a browser download for a lab document. Documents require an
 * authenticated request, so a plain `<a href>` won't work — we fetch the
 * bytes ourselves, wrap them in a blob URL, and synthesize a click.
 */
export async function downloadLabDocument(
  token: string,
  document: LabDocument,
): Promise<void> {
  const response = await fetchArtifactResponse(token, document.download_url);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement("a");
  link.href = url;
  link.download = document.source_filename || `${document.title}.txt`;
  window.document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function updateProject(
  token: string,
  projectId: string,
  data: { name?: string; description?: string | null },
): Promise<Project> {
  return apiFetch<Project>(`/api/v1/projects/${projectId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(data),
  });
}

export function deleteProject(token: string, projectId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/projects/${projectId}`, {
    method: "DELETE",
    token,
  });
}

export function updateSession(
  token: string,
  sessionId: string,
  data: {
    title?: string;
    status?: SessionStatus;
    part_type?: string | null;
    current_spec?: Record<string, unknown> | null;
  },
): Promise<DesignSession> {
  return apiFetch<DesignSession>(`/api/v1/sessions/${sessionId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(data),
  });
}

export function deleteSession(token: string, sessionId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/sessions/${sessionId}`, {
    method: "DELETE",
    token,
  });
}
