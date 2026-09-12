import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApp } from "../context/AppContext";
import { api, type RequestContext } from "./client";
import type {
  ActionOutcomeUpdate,
  ActionRequest,
  AlertOut,
  AuditLogEntry,
  CohortType,
  Granularity,
  HistoryEntry,
  MetaOut,
  OrderDetail,
  OrderFilters,
  OverrideRequest,
  PaginatedAuditLog,
  PaginatedOrders,
  ReportingResponse,
  RoleInfo,
  RuleCreate,
  RuleEvaluateResult,
  RuleOut,
  RuleUpdate,
  Tenant,
  TenantCreate,
} from "./types";

function useCtx(): RequestContext {
  const { role, tenant, actorTenant } = useApp();
  return { role, tenant, actorTenant };
}

// --- meta / tenants / roles ---

export function useMeta() {
  const ctx = useCtx();
  return useQuery({
    queryKey: ["meta", ctx.role],
    queryFn: () => api.get<MetaOut>("/meta", ctx),
  });
}

export function useTenants() {
  const ctx = useCtx();
  return useQuery({
    queryKey: ["tenants", ctx.role],
    queryFn: () => api.get<Tenant[]>("/tenants", ctx, undefined, true),
  });
}

export function useCreateTenant() {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TenantCreate) => api.post<Tenant>("/tenants", ctx, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenants"] }),
  });
}

export function useRoles() {
  const ctx = useCtx();
  return useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<RoleInfo[]>("/roles", ctx, undefined, true),
    staleTime: Infinity,
  });
}

// --- orders / queue ---

export function useOrders(filters: OrderFilters) {
  const ctx = useCtx();
  return useQuery({
    queryKey: ["orders", ctx.role, ctx.tenant, filters],
    queryFn: () => api.get<PaginatedOrders>("/orders", ctx, filters as Record<string, unknown>),
    placeholderData: (prev) => prev,
  });
}

export function useOrder(orderId: string | undefined) {
  const ctx = useCtx();
  return useQuery({
    queryKey: ["order", ctx.role, ctx.tenant, orderId],
    queryFn: () => api.get<OrderDetail>(`/orders/${orderId}`, ctx),
    enabled: !!orderId,
  });
}

export function useOrderHistory(orderId: string | undefined) {
  const ctx = useCtx();
  return useQuery({
    queryKey: ["order-history", ctx.role, ctx.tenant, orderId],
    queryFn: () => api.get<HistoryEntry[]>(`/orders/${orderId}/history`, ctx),
    enabled: !!orderId,
  });
}

export function useOverrideOrder(orderId: string) {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OverrideRequest) => api.post<OrderDetail>(`/orders/${orderId}/override`, ctx, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["order", ctx.role, ctx.tenant, orderId] });
      qc.invalidateQueries({ queryKey: ["order-history", ctx.role, ctx.tenant, orderId] });
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}

export function useCreateAction(orderId: string) {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ActionRequest) => api.post<HistoryEntry>(`/orders/${orderId}/actions`, ctx, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["order", ctx.role, ctx.tenant, orderId] });
      qc.invalidateQueries({ queryKey: ["order-history", ctx.role, ctx.tenant, orderId] });
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}

export function useUpdateActionOutcome(orderId: string) {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ logId, body }: { logId: number; body: ActionOutcomeUpdate }) =>
      api.patch<HistoryEntry>(`/orders/${orderId}/actions/${logId}`, ctx, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["order", ctx.role, ctx.tenant, orderId] });
      qc.invalidateQueries({ queryKey: ["order-history", ctx.role, ctx.tenant, orderId] });
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}

// --- reporting ---

export function useReporting(params: {
  granularity?: Granularity;
  cohort_type?: CohortType;
  cohort_key?: string;
}) {
  const ctx = useCtx();
  return useQuery({
    queryKey: ["reporting", ctx.role, ctx.tenant, params],
    queryFn: () => api.get<ReportingResponse>("/reporting/baseline-vs-actual", ctx, params),
  });
}

// --- alerts ---

export function useAlerts(params: { min_gap?: number; min_n?: number } = {}) {
  const ctx = useCtx();
  return useQuery({
    queryKey: ["alerts", ctx.role, ctx.tenant, params],
    queryFn: () => api.get<AlertOut[]>("/alerts", ctx, params),
    refetchInterval: 60_000,
  });
}

// --- rules ---

export function useRules() {
  const ctx = useCtx();
  return useQuery({
    // actorTenant is in the key because the backend filters rules by it -
    // switching which tenant you're signed in as must not reuse a cached list
    queryKey: ["rules", ctx.role, ctx.tenant, ctx.actorTenant],
    queryFn: () => api.get<RuleOut[]>("/rules", ctx),
  });
}

export function useCreateRule() {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RuleCreate) => api.post<RuleOut>("/rules", ctx, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });
}

export function useUpdateRule() {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleId, body }: { ruleId: number; body: RuleUpdate }) =>
      api.patch<RuleOut>(`/rules/${ruleId}`, ctx, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });
}

export function useEvaluateRules() {
  const ctx = useCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<RuleEvaluateResult>("/rules/evaluate", ctx),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["audit-log"] });
    },
  });
}

// --- audit log ---

export function useAuditLog(params: {
  actor_role?: string;
  event_type?: string;
  since?: string;
  until?: string;
  page?: number;
  page_size?: number;
}) {
  const ctx = useCtx();
  return useQuery({
    queryKey: ["audit-log", ctx.role, ctx.tenant, params],
    queryFn: () => api.get<PaginatedAuditLog>("/audit-log", ctx, params),
    placeholderData: (prev) => prev,
  });
}

export type { AuditLogEntry };
