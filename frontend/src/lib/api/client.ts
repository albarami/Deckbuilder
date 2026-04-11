/**
 * DeckForge API Client — fetch wrapper with typed error handling.
 *
 * All API calls go through this client. Provides:
 * - Base URL configuration via NEXT_PUBLIC_API_URL
 * - Automatic JSON serialization/deserialization
 * - Typed APIError throws for non-2xx responses
 * - Content-Type headers for JSON requests
 */

import { APIError, type APIErrorDetail } from "@/lib/types/api";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Typed fetch wrapper. Throws APIError on non-2xx responses.
 */
async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${path}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {} // Let browser set Content-Type for multipart
        : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });

  if (!response.ok) {
    // Try to parse structured error
    let errorDetail: APIErrorDetail;
    try {
      const body = await response.json();
      // Backend wraps errors in { detail: { error: { code, message } } }
      errorDetail = body?.detail?.error ?? body?.error ?? {
        code: "UNKNOWN",
        message: response.statusText,
      };
    } catch {
      errorDetail = {
        code: "UNKNOWN" as APIErrorDetail["code"],
        message: response.statusText || `HTTP ${response.status}`,
      };
    }

    throw new APIError(response.status, errorDetail);
  }

  // Handle empty responses (204 No Content)
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

/**
 * GET request.
 */
export async function get<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

/**
 * POST request with JSON body.
 */
export async function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

/**
 * POST request with FormData (multipart upload).
 */
export async function postFormData<T>(
  path: string,
  formData: FormData,
): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: formData,
  });
}

/**
 * POST request without a body.
 */
export async function postEmpty<T>(path: string): Promise<T> {
  return request<T>(path, { method: "POST" });
}

/**
 * DELETE request.
 */
export async function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}

/**
 * GET request that returns a Blob (for file downloads).
 */
export async function getBlob(
  path: string,
): Promise<{ blob: Blob; filename: string }> {
  const url = `${BASE_URL}${path}`;
  const response = await fetch(url);

  if (!response.ok) {
    let errorDetail: APIErrorDetail;
    try {
      const body = await response.json();
      errorDetail = body?.detail?.error ?? body?.error ?? {
        code: "UNKNOWN",
        message: response.statusText,
      };
    } catch {
      errorDetail = {
        code: "UNKNOWN" as APIErrorDetail["code"],
        message: response.statusText || `HTTP ${response.status}`,
      };
    }
    throw new APIError(response.status, errorDetail);
  }

  const blob = await response.blob();

  // Extract filename from Content-Disposition header
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filenameMatch = disposition.match(/filename="?([^";\s]+)"?/);
  const filename = filenameMatch?.[1] ?? "download";

  return { blob, filename };
}

export { BASE_URL };
