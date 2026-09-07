"""
serving/config.py - constants shared by the score-export layer.

This is the ONE place that defines what's real vs. synthesized in the exported
dashboard seed data. Anything added here that isn't derived from the actual
model/feature data must be an obviously-fictional stand-in (see TENANT_NAMES),
never something that could be mistaken for a real brand/date/order id.
"""

# --- source paths (relative to repo root) ---
GRAPH_DIR = "data/graph"
MODE = "train_test"
GRAPH_PATH = f"{GRAPH_DIR}/graph_{MODE}.pt"
SUB_TRAIN_PATH = f"{GRAPH_DIR}/sub_{MODE}_train.p"
SUB_TEST_PATH = f"{GRAPH_DIR}/sub_{MODE}_test.p"

# --- reproducibility (mirrors train_gnn.CONFIG) ---
SEED = 42
HIDDEN_DIM = 64
EPOCHS = 50
LR = 0.005
WEIGHT_DECAY = 5e-4

# --- synthetic display fields (NONE of these exist in the real dataset) ---
# The dataset's test period is Oct-Nov 2021 (see checkpoint_phase0_phase3.md);
# there is no per-order timestamp at all, so order dates are spread uniformly
# across this window purely for the dashboard's timeline/reporting views.
DATE_WINDOW = ("2021-10-01", "2021-11-30")

# Deliberately fictional-sounding tenant/"brand" names for the multi-tenant
# demo. These must never resemble the real (anonymized) prod__Brand_* letter
# buckets, which are a PRODUCT attribute, not a tenant/company.
TENANT_NAMES = ["Aurora Apparel", "Nimbus Fashion Co.", "Solstice Trends"]
TENANT_WEIGHTS = [0.40, 0.35, 0.25]

ORDER_ID_PREFIX = "DEMO-ORD-"

# --- reason-generation thresholds ---
HIGH_RETURN_RATE_THRESHOLD = 0.5
HIGH_RISK_SCORE_THRESHOLD = 0.7
DISCOUNT_PERCENTILE = 0.75  # computed from TRAIN split only, see reasons.py

OUTPUT_PATH = "serving/output/orders_seed.json"

PROTOTYPE_NOTICE = (
    "PROTOTYPE - illustrative data. The underlying customer/product features and "
    "model risk score are real (scored by the trained GraphSAGE model on real "
    "ASOS UK fashion return data), but order id, order date, and tenant/brand "
    "are synthesized for this demo: the dataset has no real order id, no "
    "per-order timestamp, and no multi-brand tenant structure. This is a "
    "historical-return-prediction dataset being replayed as a live RTO-risk "
    "queue for demonstration only - not a real-world RTO accuracy claim."
)
