import type { DesignResponse, ExportFormat, TemplateSpec } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

interface ApiErrorBody {
  detail?: string;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers
    },
    ...options
  });

  if (!response.ok) {
    let body: ApiErrorBody = {};
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = {};
    }
    throw new Error(body.detail ?? `API request failed with ${response.status}`);
  }

  return (await response.json()) as T;
}

export function fetchTemplates(): Promise<TemplateSpec[]> {
  return request<TemplateSpec[]>("/templates");
}

export function createDesign(
  prompt: string,
  formats: ExportFormat[] = ["stl", "step"]
): Promise<DesignResponse> {
  return request<DesignResponse>("/design", {
    method: "POST",
    body: JSON.stringify({ prompt, formats })
  });
}
