#!/usr/bin/env python3
"""
Phase 1b - Decision-Threshold Tuning for the RTO Risk Engine.

The models rank orders well (AUC ~0.69, cold-start PR-AUC ~0.60) but at the
default 0.5 cutoff they flag almost nothing - cold-customer recall was ~0.01.
That's not a model failure, it's a threshold failure: RTO is a ~30% event, so a
0.5 probability cutoff is far too high. This tool picks an operating threshold
from the precision-recall trade-off instead of defaulting to 0.5, and reports
what each choice means in rupees - which is exactly the business decision the
PRD frames (how many good orders you're willing to challenge to catch a bad one).

It retrains the chosen model (default: XGBoost, the strongest baseline), scores
the test set once, then:
  1. sweeps thresholds and prints precision / recall / F1 overall AND on the
     cold-customer slice (the slice that matters),
  2. recommends thresholds under three policies:
       - max-F1                (balanced)
       - recall >= target      (catch a set share of RTOs; default 0.60)
       - min expected cost     (uses rupee costs below),
  3. saves a threshold_sweep.csv for your own plotting / the writeup.

COST MODEL (edit to your brand's economics):
  - a MISSED RTO (false negative) costs ~Rs 300  (PRD: hard cost per RTO event)
  - a CHALLENGED GOOD order (false positive) costs an assumed friction cost:
    an order nudged to prepaid / held for confirmation that would have been fine.
    Default Rs 40 - a small fraction of the RTO cost. This ratio is the real
    lever; tune it with the brand.

Run:
    python tune_threshold.py /path/to/features
    python tune_threshold.py /path/to/features xgboost
    python tune_threshold.py /path/to/features lightgbm 0.5   # recall target 0.5
"""

import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score

CONFIG = {
    "features_dir": "./features",
    "label_col": "isReturned",
    "id_cols": ["hash(customerId)", "hash(variantID)"],
    "meta_cols": ["customer_no_history", "product_no_history"],
    "model": "xgboost",
    "random_state": 42,
    "recall_target": 0.60,
    "cost_missed_rto_inr": 300.0,    # false negative
    "cost_challenged_good_inr": 40.0,  # false positive (intervention friction)
    "thresholds": np.round(np.concatenate([np.arange(0.01, 0.10, 0.01),
                                           np.arange(0.10, 0.91, 0.05)]), 2),
}


def log(msg=""):
    print(msg)


def load_features(features_dir, name):
    return pd.read_pickle(os.path.join(features_dir, f"{name}_features.p"))


def get_xy(df, cfg):
    drop_cols = set(cfg["id_cols"] + cfg["meta_cols"] + [cfg["label_col"]])
    feat_cols = [c for c in df.columns if c not in drop_cols]
    X = df[feat_cols].astype(np.float32)
    y = df[cfg["label_col"]].astype(int)
    return X, y, feat_cols


def fit_model(name, X, y, seed):
    """Train the chosen model. Kept identical in spirit to train_baselines.py so
    the probabilities match that pipeline's."""
    if name == "xgboost":
        import xgboost as xgb
        m = xgb.XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.05,
                              subsample=0.8, colsample_bytree=0.8,
                              eval_metric="logloss", n_jobs=-1, random_state=seed)
    elif name == "lightgbm":
        import lightgbm as lgb
        m = lgb.LGBMClassifier(n_estimators=300, max_depth=6, learning_rate=0.05,
                               subsample=0.8, colsample_bytree=0.8, n_jobs=-1,
                               random_state=seed, verbose=-1)
    elif name == "catboost":
        from catboost import CatBoostClassifier
        m = CatBoostClassifier(iterations=300, depth=6, learning_rate=0.05,
                               random_seed=seed, verbose=False)
    else:
        raise SystemExit(f"unknown model '{name}' (use xgboost/lightgbm/catboost)")
    m.fit(X, y)
    return m


def sweep(y_true, y_prob, cold_mask, cfg):
    """Build the per-threshold table: precision/recall/F1 overall and on the
    cold slice, plus expected rupee cost."""
    c_fn, c_fp = cfg["cost_missed_rto_inr"], cfg["cost_challenged_good_inr"]
    rows = []
    for t in cfg["thresholds"]:
        pred = (y_prob >= t).astype(int)
        # confusion counts
        fn = int(((pred == 0) & (y_true == 1)).sum())   # missed RTOs
        fp = int(((pred == 1) & (y_true == 0)).sum())   # challenged good orders
        cost = c_fn * fn + c_fp * fp
        r = {
            "threshold": t,
            "precision": precision_score(y_true, pred, zero_division=0),
            "recall": recall_score(y_true, pred, zero_division=0),
            "f1": f1_score(y_true, pred, zero_division=0),
            "flagged_%": 100.0 * pred.mean(),
            "cold_recall": recall_score(y_true[cold_mask], pred[cold_mask], zero_division=0)
                            if cold_mask.any() else float("nan"),
            "cold_precision": precision_score(y_true[cold_mask], pred[cold_mask], zero_division=0)
                               if cold_mask.any() else float("nan"),
            "exp_cost_inr": cost,
        }
        rows.append(r)
    return pd.DataFrame(rows)


def main():
    if len(sys.argv) > 1:
        CONFIG["features_dir"] = sys.argv[1]
    if len(sys.argv) > 2:
        CONFIG["model"] = sys.argv[2].lower()
    if len(sys.argv) > 3:
        CONFIG["recall_target"] = float(sys.argv[3])

    log("=" * 70)
    log(f"PHASE 1b - THRESHOLD TUNING  (model={CONFIG['model']})")
    log("=" * 70)

    train = load_features(CONFIG["features_dir"], "train")
    test = load_features(CONFIG["features_dir"], "test")
    Xtr, ytr, _ = get_xy(train, CONFIG)
    Xte, yte, _ = get_xy(test, CONFIG)
    cold = (test["customer_no_history"].astype(bool).to_numpy()
            if "customer_no_history" in test else np.zeros(len(test), bool))
    log(f"train {Xtr.shape}, test {Xte.shape}, test RTO rate {yte.mean():.3f}, "
        f"cold customers {cold.mean():.1%}")

    model = fit_model(CONFIG["model"], Xtr, ytr, CONFIG["random_state"])
    prob = model.predict_proba(Xte)[:, 1]
    yte = yte.to_numpy()

    tbl = sweep(yte, prob, cold, CONFIG)
    log("\n--- threshold sweep ---")
    log(tbl.round(3).to_string(index=False))

    # --- policy recommendations ---
    log("\n" + "=" * 70)
    log("RECOMMENDED OPERATING POINTS")
    log("=" * 70)

    best_f1 = tbl.loc[tbl["f1"].idxmax()]
    log(f"\n[max F1]      threshold={best_f1['threshold']:.2f}  "
        f"prec={best_f1['precision']:.3f} rec={best_f1['recall']:.3f} "
        f"f1={best_f1['f1']:.3f}  flags {best_f1['flagged_%']:.1f}% of orders")

    tgt = CONFIG["recall_target"]
    hit = tbl[tbl["recall"] >= tgt]
    if len(hit):
        # lowest threshold that still hits target = highest precision at that recall
        pick = hit.loc[hit["threshold"].idxmax()]
        log(f"[recall>={tgt:.0%}]  threshold={pick['threshold']:.2f}  "
            f"prec={pick['precision']:.3f} rec={pick['recall']:.3f}  "
            f"flags {pick['flagged_%']:.1f}%  |  cold_recall={pick['cold_recall']:.3f}")
    else:
        log(f"[recall>={tgt:.0%}]  not reachable on this sweep - lower the target")

    cheap = tbl.loc[tbl["exp_cost_inr"].idxmin()]
    log(f"[min cost]    threshold={cheap['threshold']:.2f}  "
        f"expected cost=Rs {cheap['exp_cost_inr']:,.0f}  "
        f"(FN=Rs{CONFIG['cost_missed_rto_inr']:.0f}, FP=Rs{CONFIG['cost_challenged_good_inr']:.0f})  "
        f"rec={cheap['recall']:.3f} prec={cheap['precision']:.3f}")

    # cold-segment-specific: the global threshold is picked to optimize OVERALL
    # metrics, but cold-order probabilities cluster in a much lower range than
    # warm ones (imputed/generic features -> compressed scores). A single global
    # cutoff can leave cold_recall at 0 across the whole sweep above it. Compute
    # the cold slice's own best F1 threshold separately.
    if cold.any():
        cold_f1 = []
        for t in CONFIG["thresholds"]:
            pred_c = (prob[cold] >= t).astype(int)
            cold_f1.append(f1_score(yte[cold], pred_c, zero_division=0))
        tbl["cold_f1"] = cold_f1
        best_cold = tbl.loc[tbl["cold_f1"].idxmax()]
        log(f"\n[COLD-segment best F1]  threshold={best_cold['threshold']:.2f}  "
            f"cold_rec={best_cold['cold_recall']:.3f} cold_prec={best_cold['cold_precision']:.3f} "
            f"cold_f1={best_cold['cold_f1']:.3f}")
        if best_cold["threshold"] != cheap["threshold"] and best_cold["threshold"] != best_f1["threshold"]:
            log(f"  -> this differs from the overall-optimal thresholds above. Consider "
                f"a SEPARATE, lower cutoff specifically for orders flagged customer_no_history=1 "
                f"rather than one global threshold for all orders.")
    log(f"\n  vs the default 0.5 cutoff and vs flagging nothing:")
    base_none = CONFIG["cost_missed_rto_inr"] * int(yte.sum())
    row05 = tbl.iloc[(np.abs(tbl["threshold"] - 0.5)).argmin()]
    log(f"    flag nothing (all RTOs missed): Rs {base_none:,.0f}")
    log(f"    threshold 0.50               : Rs {row05['exp_cost_inr']:,.0f}  "
        f"(recall {row05['recall']:.3f})")
    log(f"    tuned min-cost threshold     : Rs {cheap['exp_cost_inr']:,.0f}  "
        f"({100*(1-cheap['exp_cost_inr']/max(base_none,1)):.0f}% below flag-nothing)")

    out = os.path.join(CONFIG["features_dir"], "threshold_sweep.csv")
    tbl.to_csv(out, index=False)
    log(f"\nsaved sweep to {out}")
    log("The cost numbers are only as right as the FN/FP rupee costs in CONFIG - "
        "set those with the brand before treating a threshold as final.")


if __name__ == "__main__":
    main()