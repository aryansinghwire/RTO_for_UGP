"""backend/app/config.py - constants for the FastAPI app."""

import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, "orders.db")
# overridable so tests can point at an isolated temp DB instead of the real one
DB_URL = os.environ.get("RTO_DASHBOARD_DB_URL", f"sqlite:///{DB_PATH}")

REPO_ROOT = os.path.dirname(BACKEND_DIR)
SEED_JSON_PATH = os.path.join(REPO_ROOT, "serving", "output", "orders_seed.json")

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# role hierarchy - a role at a given level can also do anything a lower level can.
# "tenant_admin" is scoped to a single tenant (see deps.require_tenant_scope);
# "admin" is the cross-tenant platform/support role.
ROLE_LEVELS = {
    "ops_analyst": 1,
    "tenant_admin": 2,
    "admin": 3,
}
DEFAULT_ROLE = "ops_analyst"

# spike-alert thresholds (see services/alerts.py)
ALERT_MIN_GAP = 0.15
ALERT_MIN_N = 15
