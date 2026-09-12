// Thin fetch wrapper. All requests go through Vite's dev-server proxy
// (see vite.config.ts) to the FastAPI backend at http://127.0.0.1:8000.
//
// Role is simulated via an X-Role header (no real auth in this prototype -
// see backend/app/deps.py). Tenant scoping is a `tenant` query param.

import type { Role } from "./types";

const BASE_URL = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface RequestContext {
  role: Role;
  tenant: string | null; // tenant slug being *viewed*, or null for "all tenants"
  actorTenant: string | null; // tenant the caller *belongs to* (X-Actor-Tenant)
}

function buildQuery(params: Record<string, unknown> | undefined, tenant: string | null): string {
  const search = new URLSearchParams();
  if (tenant) search.set("tenant", tenant);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        search.set(key, String(value));
      }
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

async function request<T>(
  method: "GET" | "POST" | "PATCH",
  path: string,
  ctx: RequestContext,
  options: { params?: Record<string, unknown>; body?: unknown; skipTenant?: boolean } = {},
): Promise<T> {
  const query = buildQuery(options.params, options.skipTenant ? null : ctx.tenant);
  const res = await fetch(`${BASE_URL}${path}${query}`, {
    method,
    headers: {
      "X-Role": ctx.role,
      // Stands in for the tenant claim a real session/JWT would carry. The
      // backend compares it against the tenant each request addresses, so a
      // Tenant Admin can't configure someone else's tenant.
      ...(ctx.actorTenant ? { "X-Actor-Tenant": ctx.actorTenant } : {}),
      ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data?.detail ? JSON.stringify(data.detail) : detail;
    } catch {
      // response wasn't JSON - keep statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, ctx: RequestContext, params?: Record<string, unknown>, skipTenant?: boolean) =>
    request<T>("GET", path, ctx, { params, skipTenant }),
  post: <T>(path: string, ctx: RequestContext, body?: unknown, params?: Record<string, unknown>) =>
    request<T>("POST", path, ctx, { body, params }),
  patch: <T>(path: string, ctx: RequestContext, body?: unknown, params?: Record<string, unknown>) =>
    request<T>("PATCH", path, ctx, { body, params }),
};
