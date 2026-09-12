# Project structure

Pre-Dispatch Return / RTO Risk Engine — GraphSAGE scoring pipeline plus an ops
dashboard prototype. Anything not part of that path lives in `archive/`.

```
RTO_for_UGP/
│
├── ML pipeline (produces the graph the dashboard scores)
│   ├── profile_data.py         Phase 0 — schema/join-key/cold-start profiling
│   ├── data/clean_data.py      Phase 0 — artifact fixes + paper-fidelity cleaning
│   ├── build_features.py       Phase 1 — event↔node join, role-aware imputation
│   ├── eval_harness.py         Phase 1 — shared metrics (cold-start split, leakage probe)
│   ├── train_baselines.py      Phase 1 — XGBoost / LightGBM / CatBoost / MLP floor
│   ├── sample_subgraph.py      Phase 2 — connected-subgraph sampler
│   ├── build_graph.py          Phase 2 — PyG HeteroData bipartite graph
│   └── train_gnn.py            Phase 2 — GraphSAGE  ← the shipped model
│
├── serving/                    Layer 1 — score export
│   ├── config.py               paths, seed, tenant names, reason thresholds
│   ├── synth.py                synthetic order id / date / tenant (display only)
│   ├── reasons.py              rule-based human-readable contributing reasons
│   ├── export_seed.py          trains GraphSAGE, scores test edges, writes seed JSON
│   └── output/                 orders_seed.json  (generated, gitignored)
│
├── backend/                    Layer 2 — FastAPI + SQLite
│   ├── app/
│   │   ├── main.py             app assembly, CORS, prototype marker
│   │   ├── config.py db.py models.py schemas.py deps.py constants.py
│   │   ├── routers/            meta, tenants, orders, reporting, alerts, rules, audit
│   │   └── services/           queue, reporting, alerts, rules_engine
│   ├── scripts/seed_db.py      loads seed JSON, computes baseline_stats (--force to reset)
│   ├── tests/test_api.py       smoke tests against a temp DB
│   ├── requirements.txt
│   └── orders.db               (generated, gitignored)
│
├── frontend/                   Layer 3 — React + Vite + TS + Tailwind + Recharts
│   └── src/
│       ├── api/                client.ts, hooks.ts, types.ts
│       ├── context/            AppContext.tsx (role / tenant / actor name)
│       ├── components/         queue table, filters, score badge, override + action
│       │                       forms, history timeline, score-window slider,
│       │                       alerts, rules, audit
│       └── pages/              Queue, OrderDetail, Alerts, Admin
│                               (ReportingPage is present but its route is disabled)
│
├── data/                       (gitignored — ~1.5 GB)
│   ├── *.p                     raw ASOS tables (event / customer / product × train / test)
│   ├── clean/                  cleaned tables
│   ├── features/               engineered feature tables + baseline_results.csv
│   └── graph/                  graph_train_test.pt, sub_train_test_{train,test}.p
│                               ← the three files serving/export_seed.py reads
│
├── Context/                    project reference docs (paper, PRD, findings, master context)
├── archive/                    parked work — see archive/README.md
│   ├── ablations/              Graph Transformer, Node2Vec, attention fusion
│   ├── india/                  India RTO adaptation + threshold tuning
│   ├── checkpoints/            superseded phase 1 / phase 2 write-ups
│   ├── diagnostics/            one-off Phase 0 scratch script
│   └── data/                   India / poscontrol / superseded datasets (gitignored)
│
├── checkpoint_phase0_phase3.md full technical record, phases 0–3
├── data_profile_report.md      Phase 0 profiler output
└── project_structure.md        this file
```

## Running it

```bash
# 1. regenerate the scored seed data (only needed if data/graph/ changes)
.venv/bin/python serving/export_seed.py

# 2. load it into SQLite (--force wipes and reseeds)
.venv/bin/python -m backend.scripts.seed_db

# 3. backend  (terminal 1)
.venv/bin/uvicorn backend.app.main:app --reload --port 8000

# 4. frontend (terminal 2)
cd frontend && npm run dev      # → http://localhost:5173
```
