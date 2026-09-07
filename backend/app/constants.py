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
    "ops_manager": {
        "label": "Ops Manager / Brand Admin",
        "description": "Everything an Ops Analyst can do, plus configuring automated rules, viewing reporting/alerts, and the audit log.",
    },
    "admin": {
        "label": "Support / Admin",
        "description": "Everything an Ops Manager can do, plus onboarding new tenants.",
    },
}
