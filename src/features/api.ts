import type { components } from "../../packages/contracts/openapi";

export type User = components["schemas"]["UserView"];
export type Case = components["schemas"]["ApplicationView"];
export type Evidence = components["schemas"]["EvidenceView"];
export type Institution = components["schemas"]["InstitutionView"];
export type Preview = components["schemas"]["PreviewView"];
export interface ApiResult<T> {
  data: T;
  meta: { request_id: string; page?: number; total?: number };
  error: null;
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fields: Record<string, string> = {},
  ) {
    super(message);
  }
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<ApiResult<T>> {
  const csrf =
    document.cookie
      .split("; ")
      .find((x) => x.startsWith("uv_csrf="))
      ?.slice(8) ?? "";
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf,
      ...options.headers,
    },
  });
  let body;
  try {
    body = await response.json();
  } catch {
    throw new ApiError(503, "The API could not be reached. Check the API server and try again.");
  }
  if (!response.ok && response.status === 401 && !["/auth/session", "/me"].includes(path))
    window.dispatchEvent(new Event("uranium:session-expired"));
  if (!response.ok || body.error)
    throw new ApiError(
      response.ok ? 503 : response.status,
      body.error?.message ?? "Request failed.",
      body.error?.field_errors ?? {},
    );
  return body;
}
