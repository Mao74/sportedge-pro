/**
 * Typed API client. Reads the access token from the auth store, attaches
 * it as a Bearer header, and lifts RFC 9457 problem-details responses into
 * a typed ``ApiError`` exception.
 *
 * Strongly-typed request/response shapes for individual endpoints will be
 * generated from the backend OpenAPI schema (step 9 onward via
 * openapi-typescript). For now, callers pass explicit generics.
 */

import { useAuthStore } from '@/stores/auth';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
  errors?: unknown;
  [k: string]: unknown;
}

export class ApiError extends Error {
  status: number;
  problem: ProblemDetails;
  constructor(problem: ProblemDetails) {
    super(problem.detail || problem.title);
    this.name = 'ApiError';
    this.status = problem.status;
    this.problem = problem;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null | string[]>;
  signal?: AbortSignal;
  /** When false, do not attach the access token (used by /auth/login). */
  authed?: boolean;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null) continue;
      if (Array.isArray(value)) {
        for (const v of value) url.searchParams.append(key, String(v));
      } else {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.pathname + url.search;
}

export async function apiRequest<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, signal, authed = true } = opts;
  const headers: Record<string, string> = { Accept: 'application/json' };

  if (authed) {
    const token = useAuthStore.getState().accessToken;
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let serializedBody: string | undefined;
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    serializedBody = JSON.stringify(body);
  }

  const resp = await fetch(buildUrl(path, query), {
    method,
    headers,
    body: serializedBody,
    signal,
  });

  if (resp.status === 204) return undefined as T;

  const text = await resp.text();
  const data = text ? JSON.parse(text) : null;

  if (!resp.ok) {
    const problem: ProblemDetails =
      data && typeof data === 'object'
        ? data
        : { type: 'about:blank', title: resp.statusText, status: resp.status };
    if (problem.status === 401) {
      // Token rejected — clear and let ProtectedRoute redirect.
      useAuthStore.getState().clear();
    }
    throw new ApiError(problem);
  }

  return data as T;
}

// --- Convenience method-bound helpers --------------------------------------

export const api = {
  get: <T>(path: string, query?: RequestOptions['query'], signal?: AbortSignal) =>
    apiRequest<T>(path, { method: 'GET', query, signal }),
  post: <T>(path: string, body?: unknown, query?: RequestOptions['query']) =>
    apiRequest<T>(path, { method: 'POST', body, query }),
  patch: <T>(path: string, body?: unknown, query?: RequestOptions['query']) =>
    apiRequest<T>(path, { method: 'PATCH', body, query }),
  delete: <T>(path: string, query?: RequestOptions['query']) =>
    apiRequest<T>(path, { method: 'DELETE', query }),
};
