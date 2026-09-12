"""backend/app/constants.py - small fixed vocabularies used across routers."""

ACTION_TYPES = {
    "call_customer",
    "send_confirmation_sms",
    "send_reminder_email",
    "flag_for_manual_review",
    "convert_cod_to_prepaid",
}

OUTCOMES = {"pending", "resolved_kept", "resolved_prevented", "no_response"}

CLOSING_OUTCOMES = {"resolved_kept", "resolved_prevented", "no_response"}

ORDER_STATUSES = {"pending", "overridden", "actioned", "closed"}

ROLES = {
    "ops_analyst": {
        "label": "Ops Analyst",
        "description": "Reviews the risk queue, drills into orders, applies manual overrides and logs interventions.",
    },
    "tenant_admin": {
        "label": "Tenant Admin",
        "description": "Everything an Ops Analyst can do, for their own tenant only: configuring that tenant's automated score windows, alerts, and audit log.",
    },
    "admin": {
        "label": "Platform Admin (Support)",
        "description": "Cross-tenant. Everything a Tenant Admin can do for any tenant, plus onboarding new tenants.",
    },
}
