"""
eval_harness.py - Reusable evaluation harness for the Returnformer / RTO Risk
Engine build. Import this from train_baselines.py and, later, from the GNN /
Returnformer training scripts, so every model in every phase is scored the
same way.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score,
)


def compute_metrics(y_true, y_prob, threshold=0.5):
    """Standard metric set: Accuracy, Precision, Recall, F1, AUC, PR-AUC (AP).
    Matches the paper's Figure 8/9/12 metric choices."""
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    y_pred = (y_prob >= threshold).astype(int)
    n_pos = int(y_true.sum())
    if n_pos == 0 or n_pos == len(y_true):
        return {"accuracy": accuracy_score(y_true, y_pred), "precision": None,
                "recall": None, "f1": None, "auc": None, "pr_auc": None,
                "n": len(y_true), "n_pos": n_pos,
                "note": "single-class slice - ranking metrics undefined"}
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "auc": roc_auc_score(y_true, y_prob),
        "pr_auc": average_precision_score(y_true, y_prob),
        "n": len(y_true),
        "n_pos": n_pos,
    }


def format_metrics(m, label=""):
    if m.get("precision") is None:
        return f"{label}: n={m['n']:,} ({m['n_pos']} positive) - {m.get('note', 'skipped')}"
    return (f"{label}: acc={m['accuracy']:.4f}  prec={m['precision']:.4f}  "
            f"rec={m['recall']:.4f}  f1={m['f1']:.4f}  "
            f"auc={m['auc']:.4f}  pr_auc={m['pr_auc']:.4f}  (n={m['n']:,})")


def high_return_slice_metrics(y_true, y_prob, customer_return_rate, threshold_rate=0.5):
    """Reproduces the paper's Table 4: metrics on the subset of events whose
    customer has a historical return rate >= threshold_rate."""
    mask = np.asarray(customer_return_rate) >= threshold_rate
    if mask.sum() == 0:
        return None
    return compute_metrics(np.asarray(y_true)[mask], np.asarray(y_prob)[mask])


def cold_start_split_metrics(y_true, y_prob, no_history_flag):
    """Split metrics by whether the ORPHAN imputation fired for this edge -
    i.e. compare model performance on warm (real history) vs cold (imputed)
    orders. This is the check the paper doesn't need but the PRD does, since
    the PRD's cold-start fallback model is judged on exactly this split."""
    flag = np.asarray(no_history_flag).astype(bool)
    y_true, y_prob = np.asarray(y_true), np.asarray(y_prob)
    out = {}
    if (~flag).sum() > 0:
        out["warm"] = compute_metrics(y_true[~flag], y_prob[~flag])
    if flag.sum() > 0:
        out["cold"] = compute_metrics(y_true[flag], y_prob[flag])
    return out


def leakage_probe(df, candidate_cols, label_col):
    """Single-feature ranking AUC for each candidate column, computed by using
    the raw column value directly as a score (no model fit needed). A value
    close to 0.5 is uninformative; a MODERATELY high value (e.g. 0.65-0.85)
    is expected for genuine signal like a return-rate feature; a value very
    close to 1.0 is the red flag - it suggests the column was computed with
    information from the period you're trying to predict.

    This is a diagnostic to READ, not a pass/fail gate - a strong feature is
    supposed to be predictive. Report it, don't auto-reject on it.
    """
    y = df[label_col].values
    rows = []
    for c in candidate_cols:
        if c not in df.columns:
            continue
        try:
            auc = roc_auc_score(y, df[c].values)
        except Exception:
            continue
        rows.append((c, auc))
    rows.sort(key=lambda x: -x[1])
    return pd.DataFrame(rows, columns=["column", "single_feature_auc"])


def full_report(model_name, y_true, y_prob, customer_return_rate=None,
                 customer_no_history=None, product_no_history=None):
    """Runs the full evaluation suite for one model and prints it."""
    print(f"\n{'=' * 60}\n{model_name}\n{'=' * 60}")
    overall = compute_metrics(y_true, y_prob)
    print(format_metrics(overall, "overall"))

    if customer_return_rate is not None:
        hr = high_return_slice_metrics(y_true, y_prob, customer_return_rate)
        if hr is not None:
            print(format_metrics(hr, "high-return customers (>=50%)"))

    if customer_no_history is not None:
        cs = cold_start_split_metrics(y_true, y_prob, customer_no_history)
        for k, m in cs.items():
            print(format_metrics(m, f"customer cold-start = {k}"))

    if product_no_history is not None:
        cs = cold_start_split_metrics(y_true, y_prob, product_no_history)
        for k, m in cs.items():
            print(format_metrics(m, f"product cold-start = {k}"))

    return overall
