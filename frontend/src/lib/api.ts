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

function buildApiUrl(path: string): string {
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
  part_type: string | null;
  current_spec: Record<string, unknown> | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

// API calls
export function fetchCurrentUser(token: string): Promise<UserProfile> {
  return apiFetch<UserProfile>("/api/v1/auth/me", { token });
}

export function fetchLabs(token: string): Promise<Lab[]> {
  return apiFetch<Lab[]>("/api/v1/labs", { token });
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

export function createSession(
  token: string,
  projectId: string,
  data: { title: string; part_type?: string | null; current_spec?: Record<string, unknown> | null },
): Promise<DesignSession> {
  return apiFetch<DesignSession>(`/api/v1/projects/${projectId}/sessions`, {
    method: "POST",
    token,
    body: JSON.stringify(data),
  });
}
