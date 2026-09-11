// Mirrors backend/app/schemas.py and backend/app/constants.py exactly.

export type Role = "ops_analyst" | "ops_manager" | "admin";

export const ROLE_LEVELS: Record<Role, number> = {
  ops_analyst: 1,
  ops_manager: 2,
  admin: 3,
};

export interface RoleInfo {
  role: Role;
  label: string;
  description: string;
}

export interface Tenant {
  id: number;
  name: string;
  slug: string;
}

export interface TenantCreate {
  name: string;
}

export const ACTION_TYPES = [
  "call_customer",
  "send_confirmation_sms",
  "send_reminder_email",
  "flag_for_manual_review",
  "convert_cod_to_prepaid",
] as const;
export type ActionType = (typeof ACTION_TYPES)[number];

export const OUTCOMES = ["pending", "resolved_kept", "resolved_prevented", "no_response"] as const;
export type Outcome = (typeof OUTCOMES)[number];

export const ORDER_STATUSES = ["pending", "overridden", "actioned", "closed"] as const;
export type OrderStatusValue = (typeof ORDER_STATUSES)[number];

export interface OrderListItem {
  order_id: string;
  tenant: string;
  order_date: string;
  customer_ref: string;
  product_ref: string;
  current_score: number;
  model_risk_score: number;
  status: OrderStatusValue;
  reasons: string[];
  customer_no_history: boolean;
  product_no_history: boolean;
  country_bucket: string;
  product_brand_bucket: string;
  product_type_bucket: string;
}

export interface OrderDetail extends OrderListItem {
  customer_return_rate: number;
  product_return_rate: number;
  avg_discount_value: number;
  avg_gbp_price: number;
  override_score: number | null;
  override_reason: string | null;
  overridden_by: string | null;
  overridden_at: string | null;
  raw_features: Record<string, unknown>;
}

export interface PaginatedOrders {
  items: OrderListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface OrderFilters {
  tenant?: string;
  status?: OrderStatusValue;
  min_score?: number;
  max_score?: number;
  country?: string;
  product_type?: string;
  cold_start?: boolean;
  sort?: "score" | "-score" | "date" | "-date";
  page?: number;
  page_size?: number;
}

export interface OverrideRequest {
  new_score: number;
  reason: string;
  actor_name?: string;
}

export interface ActionRequest {
  action_type: ActionType;
  trigger?: "manual" | "automated_threshold";
  note?: string;
  actor_name?: string;
}

export interface ActionOutcomeUpdate {
  outcome: Outcome;
  note?: string;
}

export interface HistoryEntry {
  id: number;
  event_type: "override" | "intervention_action";
  action_type: ActionType | null;
  trigger: "manual" | "automated_threshold";
  outcome: Outcome | null;
  old_score: number | null;
  new_score: number | null;
  note: string | null;
  actor_role: Role;
  actor_name: string | null;
  created_at: string;
}

export interface AuditLogEntry extends HistoryEntry {
  order_id: string;
  tenant: string;
}

export interface PaginatedAuditLog {
  items: AuditLogEntry[];
  page: number;
  page_size: number;
  total: number;
}

export interface ReportingBucket {
  bucket: string;
  baseline_return_rate: number;
  actual_return_rate: number;
  n_orders: number;
}

export type CohortType = "overall" | "product" | "country" | "product_type";
export type Granularity = "day" | "week";

export interface ReportingResponse {
  cohort_type: CohortType;
  cohort_key: string;
  granularity: Granularity;
  buckets: ReportingBucket[];
}

export interface AlertOut {
  tenant: string;
  cohort_type: CohortType;
  cohort_key: string;
  baseline_rate: number;
  actual_rate: number;
  gap: number;
  n_orders: number;
  severity: "high" | "medium";
}

export interface RuleOut {
  id: number;
  tenant: string;
  name: string;
  score_threshold: number;
  action_type: ActionType;
  is_active: boolean;
}

export interface RuleCreate {
  name: string;
  score_threshold: number;
  action_type: ActionType;
}

export interface RuleUpdate {
  is_active?: boolean;
  score_threshold?: number;
  action_type?: ActionType;
}

export interface RuleEvaluateResult {
  rules_evaluated: number;
  actions_created: number;
  details: { rule: string; actions_created: number }[];
}

export interface MetaOut {
  generated_at: string;
  model: string;
  n_orders: number;
  achieved_overall_auc: number | null;
  achieved_cold_customer_auc: number | null;
  tenants: string[];
  notice: string;
}
