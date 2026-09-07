#!/usr/bin/env python3
"""
serving/export_seed.py - Layer 1 of the ops-dashboard prototype.

Trains the validated GraphSAGE model (same architecture/config as
train_gnn.py, imported not duplicated) on the existing sampled subgraph,
scores the held-out test edges, and joins those scores back onto the raw,
human-readable test-edge feature rows to produce a single seed JSON document
for the backend (Layer 2) to load.

Does NOT modify train_gnn.py or any other existing ML script. Re-states the
load/train/score orchestration train_gnn.py's main() already does for
train_test mode, because train_gnn.py has no importable train_and_score()
function - only its Model/GNNEncoder/EdgeDecoder classes are imported here.

Run:
    .venv/bin/python serving/export_seed.py
"""

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from train_gnn import Model  # noqa: E402  (repo-root script, imported not duplicated)
from eval_harness import full_report, cold_start_split_metrics  # noqa: E402

import config  # noqa: E402
import synth  # noqa: E402
from reasons import derive_reasons  # noqa: E402


def log(msg=""):
    print(msg)


def to_native(value):
    """Make a value JSON-serializable (numpy scalars -> python scalars)."""
    if isinstance(value, (np.generic,)):
        return value.item()
    if isinstance(value, (np.ndarray,)):
        return value.tolist()
    return value


def decode_bucket(row, cols):
    """Given a set of one-hot columns sharing a prefix (e.g. cust__Country_*),
    return the active bucket's short name (e.g. "Country_C"), or "Unknown" if
    none fired (this happens for orphan/no-history rows, which are zero-filled
    by build_features.py's imputation)."""
    for c in cols:
        if row[c] >= 0.5:
            return c.split("__", 1)[1]
    return "Unknown"


def train_and_score():
    """Mirrors train_gnn.py's main() for mode='train_test' exactly (same
    architecture, same CONFIG values, same seed) so the exported scores come
    from the same model the project validated - just also persisted here,
    which train_gnn.py itself never does."""
    torch.manual_seed(config.SEED)
    np.random.seed(config.SEED)

    data = torch.load(config.GRAPH_PATH, weights_only=False)
    edge = data["customer", "buys", "product"]
    log(data)

    train_mask = edge.train_mask
    test_mask = edge.test_mask
    y = edge.edge_label

    has_edge_attr = "edge_attr" in edge
    edge_dim = edge.edge_attr.size(1) if has_edge_attr else 0
    edge_attr_train = edge.edge_attr[train_mask] if has_edge_attr else None
    edge_attr_test = edge.edge_attr[test_mask] if has_edge_attr else None
    log(f"edge_attr present: {has_edge_attr} (edge_dim={edge_dim})")

    mp_edge_index = edge.edge_index[:, train_mask]
    x_dict = {"customer": data["customer"].x, "product": data["product"].x}
    edge_index_dict = {
        ("customer", "buys", "product"): mp_edge_index,
        ("product", "rev_buys", "customer"): mp_edge_index.flip(0),
    }

    model = Model(data.metadata(), config.HIDDEN_DIM, edge_dim=edge_dim)
    opt = torch.optim.Adam(model.parameters(), lr=config.LR,
                            weight_decay=config.WEIGHT_DECAY)

    train_ei = edge.edge_index[:, train_mask]
    test_ei = edge.edge_index[:, test_mask]
    y_train = y[train_mask]
    y_test = y[test_mask]

    pos_weight = ((y_train == 0).sum() / (y_train == 1).sum().clamp(min=1)).clamp(0.2, 5.0)

    log(f"\ntraining {config.EPOCHS} epochs "
        f"({train_mask.sum().item():,} train edges, {test_mask.sum().item():,} test edges)")
    model.train()
    for ep in range(1, config.EPOCHS + 1):
        opt.zero_grad()
        out = model(x_dict, edge_index_dict, train_ei, edge_attr_train)
        loss = F.binary_cross_entropy_with_logits(out, y_train, pos_weight=pos_weight)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        opt.step()
        if ep % 10 == 0 or ep == 1:
            log(f"  epoch {ep:3d}  loss {loss.item():.4f}")

    model.eval()
    with torch.no_grad():
        test_logits = model(x_dict, edge_index_dict, test_ei, edge_attr_test)
        test_prob = torch.sigmoid(test_logits).numpy()

    y_test_np = y_test.numpy()
    cust_no_hist = edge.customer_no_history[test_mask].numpy() if "customer_no_history" in edge else None
    prod_no_hist = edge.product_no_history[test_mask].numpy() if "product_no_history" in edge else None
    cust_rr = edge.cust_return_rate[test_mask].numpy() if "cust_return_rate" in edge else None

    overall = full_report("GraphSAGE (train_test) - serving export",
                           y_test_np, test_prob,
                           customer_return_rate=cust_rr,
                           customer_no_history=cust_no_hist,
                           product_no_history=prod_no_hist)

    cold_metrics = cold_start_split_metrics(y_test_np, test_prob, cust_no_hist) if cust_no_hist is not None else {}
    achieved_cold_auc = cold_metrics.get("cold", {}).get("auc")

    log(f"\nAchieved this run: overall AUC={overall.get('auc')}, "
        f"cold-customer AUC={achieved_cold_auc} "
        f"(checkpoint reference: 0.876 / 0.767 - some run-to-run drift is expected, "
        f"not a bug if close but not identical)")

    return test_prob, y_test_np, overall, achieved_cold_auc


def build_seed_records(test_prob):
    display_df = pd.read_pickle(config.SUB_TEST_PATH).reset_index(drop=True)

    # --- row-order invariant: this is the whole join mechanism, verify it every run ---
    assert len(display_df) == len(test_prob), (
        f"row-order mismatch: {len(display_df)} display rows vs {len(test_prob)} scores - "
        "the positional join assumption (see checkpoint notes) is broken, do not proceed"
    )
    if len(display_df) != 16246:
        log(f"NOTE: expected 16,246 test rows per the existing sampled subgraph, got "
            f"{len(display_df)} - fine if you've regenerated sample_subgraph.py with "
            f"different parameters, otherwise investigate.")

    display_df["risk_score"] = test_prob

    # hash IDs exceed Number.MAX_SAFE_INTEGER in JS - must be strings, not numbers
    display_df["hash(customerId)"] = display_df["hash(customerId)"].astype(str)
    display_df["hash(variantID)"] = display_df["hash(variantID)"].astype(str)

    n = len(display_df)
    display_df["order_id"] = synth.make_order_ids(n)
    display_df["order_date"] = synth.make_order_dates(n, seed=config.SEED)
    display_df["tenant"] = synth.assign_tenants(display_df["hash(customerId)"], seed=config.SEED)

    # discount threshold computed from TRAIN split only, to avoid leaking the
    # test distribution into what counts as "a deep discount"
    train_df = pd.read_pickle(config.SUB_TRAIN_PATH)
    discount_p75_train = float(train_df["prod__avgDiscountValue"].quantile(config.DISCOUNT_PERCENTILE))

    country_cols = [c for c in display_df.columns if c.startswith("cust__Country_")]
    brand_cols = [c for c in display_df.columns if c.startswith("prod__Brand_")]
    ptype_cols = [c for c in display_df.columns if c.startswith("prod__productType_")]

    cust_reason_cols = [c for c in display_df.columns
                         if c.startswith("cust__customerId_level_return_code_")]
    prod_reason_cols = [c for c in display_df.columns
                         if c.startswith("prod__variantID_level_return_code_")]

    records = []
    nan_found = False
    for _, row in display_df.iterrows():
        risk_score = float(row["risk_score"])
        reasons = derive_reasons(row, risk_score, discount_p75_train)

        curated_raw = {
            "age": to_native(row["cust__age"]),
            "yearOfBirth": to_native(row["cust__yearOfBirth"]),
            "isMale": to_native(row["cust__isMale"]),
            "premier": to_native(row["cust__premier"]),
            "salesPerCustomer": to_native(row["cust__salesPerCustomer"]),
            "returnsPerCustomer": to_native(row["cust__returnsPerCustomer"]),
            "salesPerProduct": to_native(row["prod__salesPerProduct"]),
            "returnsPerProduct": to_native(row["prod__returnsPerProduct"]),
            "customer_return_reason_profile": {
                c.split("_")[-1]: to_native(row[c]) for c in cust_reason_cols
            },
            "product_return_reason_profile": {
                c.split("_")[-1]: to_native(row[c]) for c in prod_reason_cols
            },
        }

        record = {
            "order_id": row["order_id"],
            "tenant": row["tenant"],
            "order_date": row["order_date"],
            "customer_ref": row["hash(customerId)"],
            "product_ref": row["hash(variantID)"],
            "risk_score": risk_score,
            "reasons": reasons,
            "customer_no_history": int(row["customer_no_history"]),
            "product_no_history": int(row["product_no_history"]),
            "customer_return_rate": float(row["cust__customerReturnRate"]),
            "product_return_rate": float(row["prod__productReturnRate"]),
            "avg_discount_value": float(row["prod__avgDiscountValue"]),
            "avg_gbp_price": float(row["prod__avgGbpPrice"]),
            "country_bucket": decode_bucket(row, country_cols),
            "product_brand_bucket": decode_bucket(row, brand_cols),
            "product_type_bucket": decode_bucket(row, ptype_cols),
            "raw_features": curated_raw,
            # never surfaced on the live order-detail endpoint - aggregate use only
            "is_returned_ground_truth": int(row["isReturned"]),
        }

        for k in ("risk_score", "customer_return_rate", "product_return_rate",
                  "avg_discount_value", "avg_gbp_price"):
            if not np.isfinite(record[k]):
                nan_found = True

        records.append(record)

    assert not nan_found, "NaN/Inf found in exported numeric fields - investigate before writing JSON"
    return records


def main():
    test_prob, y_test_np, overall, achieved_cold_auc = train_and_score()
    records = build_seed_records(test_prob)

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "GraphSAGE (train_test)",
        "seed": config.SEED,
        "n_orders": len(records),
        "achieved_overall_auc": to_native(overall.get("auc")),
        "achieved_cold_customer_auc": to_native(achieved_cold_auc),
        "source_files": [config.GRAPH_PATH, config.SUB_TEST_PATH],
        "tenants": config.TENANT_NAMES,
        "notice": config.PROTOTYPE_NOTICE,
    }

    os.makedirs(os.path.dirname(config.OUTPUT_PATH), exist_ok=True)
    with open(config.OUTPUT_PATH, "w") as f:
        json.dump({"meta": meta, "orders": records}, f, indent=2)

    log(f"\nwrote {len(records):,} orders to {config.OUTPUT_PATH}")
    log(f"tenant split: {pd.Series([r['tenant'] for r in records]).value_counts(normalize=True).to_dict()}")
    log(f"date range: {min(r['order_date'] for r in records)} to "
        f"{max(r['order_date'] for r in records)}")


if __name__ == "__main__":
    main()
