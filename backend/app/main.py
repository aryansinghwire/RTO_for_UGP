"""backend/app/main.py - FastAPI app assembly.

Run:
    .venv/bin/uvicorn backend.app.main:app --reload --port 8000
(from the repo root, after running backend/scripts/seed_db.py at least once)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from .config import CORS_ORIGINS
from .db import Base, engine
from .routers import alerts, audit, meta, orders, reporting, rules, tenants


def _drop_stale_rules_table() -> None:
    """automated_rules moved from a single `score_threshold` to a
    `score_min`/`score_max` window. There are no migrations in this prototype
    (create_all only), so a database written before that change would keep the
    old column and every rule query would fail.

    Rules are configuration a user types in, not seeded data, so dropping just
    this one table is safe and self-healing: orders, overrides and the audit
    log are untouched. Only stored rules are lost, and only once.
    """
    inspector = inspect(engine)
    if "automated_rules" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("automated_rules")}
    if "score_threshold" in columns:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE automated_rules"))


_drop_stale_rules_table()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Pre-Dispatch Return/RTO Risk Engine - Ops Dashboard Prototype")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_prototype_marker(request, call_next):
    """Every response carries a machine-detectable marker that this is
    prototype/illustrative data, not a real production RTO system (see
    /api/meta for the full human-readable notice)."""
    response = await call_next(request)
    response.headers["X-Prototype"] = "true"
    return response


app.include_router(meta.router, prefix="/api")
app.include_router(tenants.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(reporting.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
