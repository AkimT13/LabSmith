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

// API calls
export function fetchCurrentUser(token: string): Promise<UserProfile> {
  return apiFetch<UserProfile>("/api/v1/auth/me", { token });
}
