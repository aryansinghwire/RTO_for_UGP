#!/usr/bin/env python3
"""
Phase 1 - Baseline Models for the Returnformer / RTO Risk Engine build.

Trains the four tabular baselines the paper (and PRD Section 12) compares
against: XGBoost, LightGBM, CatBoost, MLP. Evaluates each with eval_harness -
overall metrics, the paper's Table-4-style high-return-customer slice, and a
cold-start split (warm vs imputed/orphan orders) that the paper doesn't need
but the PRD does, since the cold-start fallback model is judged on exactly
that split.

These are NOT tuned (no Optuna sweep, unlike the paper's Section 4.1) -
reasonable defaults only. Getting a working, comparable baseline is the goal
here; tuning is a later refinement once the pipeline is proven correct.

Run:
    python train_baselines.py /path/to/features_out
    python train_baselines.py /path/to/features_out lightgbm        # one model
    python train_baselines.py /path/to/features_out xgboost,lightgbm # a subset
    python train_baselines.py /path/to/features_out lightgbm 50000  # + a fast
        # dry run: trains on only 50,000 REAL rows (still evaluates on the
        # full test set) so you can catch problems in ~seconds, not minutes,
        # before committing to a full-data run.
"""

import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from eval_harness import full_report, leakage_probe

CONFIG = {
    "features_dir": "./features",
    "label_col": "isReturned",
    "id_cols": ["hash(customerId)", "hash(variantID)"],
    "meta_cols": ["customer_no_history", "product_no_history"],  # kept for
        # reporting/slicing, excluded from the model's X matrix
    "mlp_max_rows": 200_000,  # sklearn's MLP has no GPU/minibatch scheduling
        # here; subsample for it specifically if the full set is large. Trees
        # (xgb/lgbm/catboost) train on the full data - no such cap for them.
    "random_state": 42,
    # which models to run - edit this list, or pass a comma-separated arg
    # (e.g. "lightgbm" or "xgboost,catboost") to override without editing.
    "models": ["xgboost", "lightgbm", "catboost", "mlp"],
    # if set, subsample the TRAINING set to this many real rows for a fast
    # dry run (catches crashes/memory issues in seconds). Test set always
    # stays full size - evaluation is cheap, and you want a real score.
    "sample_rows": None,
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


def find_customer_return_rate_col(feat_cols):
    for c in feat_cols:
        if c.lower() == "cust__customerreturnrate":
            return c
    for c in feat_cols:
        if "customer" in c.lower() and "returnrate" in c.lower():
            return c
    return None


def main():
    if len(sys.argv) > 1:
        CONFIG["features_dir"] = sys.argv[1]
    if len(sys.argv) > 2:
        CONFIG["models"] = [m.strip().lower() for m in sys.argv[2].split(",")]
    if len(sys.argv) > 3:
        CONFIG["sample_rows"] = int(sys.argv[3])

    log("=" * 70)
    log("PHASE 1 - BASELINE MODELS")
    log(f"features_dir: {os.path.abspath(CONFIG['features_dir'])}")
    log(f"models to run: {CONFIG['models']}")
    log("=" * 70)

    train_df = load_features(CONFIG["features_dir"], "train")
    test_df = load_features(CONFIG["features_dir"], "test")
    log(f"train: {train_df.shape}   test: {test_df.shape}")

    X_train, y_train, feat_cols = get_xy(train_df, CONFIG)
    X_test, y_test, _ = get_xy(test_df, CONFIG)
    log(f"feature columns: {len(feat_cols)}")

    if CONFIG["sample_rows"] and len(X_train) > CONFIG["sample_rows"]:
        idx = np.random.RandomState(CONFIG["random_state"]).choice(
            len(X_train), CONFIG["sample_rows"], replace=False)
        X_train_fit, y_train_fit = X_train.iloc[idx], y_train.iloc[idx]
        log(f"DRY RUN: sampling training set {len(X_train):,} -> "
            f"{len(X_train_fit):,} rows (test set stays full at {len(X_test):,})")
    else:
        X_train_fit, y_train_fit = X_train, y_train

    # --- leakage probe on the single most suspect features ---
    log("\n--- leakage probe (single-feature ranking AUC) ---")
    probe_cols = [c for c in feat_cols if "returnrate" in c.lower()]
    probe = leakage_probe(train_df, probe_cols, CONFIG["label_col"])
    log(probe.to_string(index=False))
    log("(0.5 = uninformative. ~0.6-0.85 = genuine signal, expected for a")
    log(" return-rate feature. Very close to 1.0 would suggest the column")
    log(" was computed using information from the window you're predicting.)")

    cust_rr_col = find_customer_return_rate_col(feat_cols)
    cust_no_hist_test = test_df["customer_no_history"] if "customer_no_history" in test_df else None
    prod_no_hist_test = test_df["product_no_history"] if "product_no_history" in test_df else None
    cust_rr_test = test_df[cust_rr_col] if cust_rr_col else None

    results = {}

    # --- XGBoost ---
    if "xgboost" in CONFIG["models"]:
        import xgboost as xgb
        log("\ntraining XGBoost...")
        t0 = time.time()
        xgb_model = xgb.XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, eval_metric="logloss",
            n_jobs=-1, random_state=CONFIG["random_state"],
        )
        xgb_model.fit(X_train_fit, y_train_fit)
        xgb_prob = xgb_model.predict_proba(X_test)[:, 1]
        log(f"  done in {time.time() - t0:.1f}s")
        results["XGBoost"] = full_report("XGBoost", y_test, xgb_prob,
                                          cust_rr_test, cust_no_hist_test, prod_no_hist_test)

    # --- LightGBM ---
    if "lightgbm" in CONFIG["models"]:
        import lightgbm as lgb
        log("\ntraining LightGBM...")
        t0 = time.time()
        lgb_model = lgb.LGBMClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            n_jobs=-1, random_state=CONFIG["random_state"], verbose=-1,
        )
        lgb_model.fit(X_train_fit, y_train_fit)
        lgb_prob = lgb_model.predict_proba(X_test)[:, 1]
        log(f"  done in {time.time() - t0:.1f}s")
        results["LightGBM"] = full_report("LightGBM", y_test, lgb_prob,
                                           cust_rr_test, cust_no_hist_test, prod_no_hist_test)

    # --- CatBoost ---
    if "catboost" in CONFIG["models"]:
        from catboost import CatBoostClassifier
        log("\ntraining CatBoost...")
        t0 = time.time()
        cb_model = CatBoostClassifier(
            iterations=300, depth=6, learning_rate=0.05,
            random_seed=CONFIG["random_state"], verbose=False,
        )
        cb_model.fit(X_train_fit, y_train_fit)
        cb_prob = cb_model.predict_proba(X_test)[:, 1]
        log(f"  done in {time.time() - t0:.1f}s")
        results["CatBoost"] = full_report("CatBoost", y_test, cb_prob,
                                           cust_rr_test, cust_no_hist_test, prod_no_hist_test)

    # --- MLP ---
    if "mlp" in CONFIG["models"]:
        log("\ntraining MLP...")
        t0 = time.time()
        if len(X_train_fit) > CONFIG["mlp_max_rows"]:
            log(f"  subsampling train to {CONFIG['mlp_max_rows']:,} rows for MLP "
                f"(sklearn's MLP has no GPU/minibatch tuning here - the full "
                f"{len(X_train_fit):,}-row set would be slow. Trees above "
                f"trained on that full set.)")
            idx = np.random.RandomState(CONFIG["random_state"]).choice(
                len(X_train_fit), CONFIG["mlp_max_rows"], replace=False)
            X_mlp, y_mlp = X_train_fit.iloc[idx], y_train_fit.iloc[idx]
        else:
            X_mlp, y_mlp = X_train_fit, y_train_fit

        scaler = StandardScaler()
        X_mlp_s = scaler.fit_transform(X_mlp)
        X_test_s = scaler.transform(X_test)
        mlp_model = MLPClassifier(
            hidden_layer_sizes=(128, 64), max_iter=100, early_stopping=True,
            random_state=CONFIG["random_state"],
        )
        mlp_model.fit(X_mlp_s, y_mlp)
        mlp_prob = mlp_model.predict_proba(X_test_s)[:, 1]
        log(f"  done in {time.time() - t0:.1f}s")
        results["MLP"] = full_report("MLP", y_test, mlp_prob,
                                      cust_rr_test, cust_no_hist_test, prod_no_hist_test)

    if not results:
        log("\nNo models matched CONFIG['models'] / the CLI arg - nothing trained.")
        log("Valid names: xgboost, lightgbm, catboost, mlp")
        return

    # --- comparison table (mirrors the paper's Figure 8) ---
    log("\n" + "=" * 70)
    log("COMPARISON (overall test-set metrics)")
    log("=" * 70)
    comp = pd.DataFrame(results).T[["accuracy", "precision", "recall", "f1", "auc", "pr_auc"]]
    log(comp.round(4).to_string())
    comp.to_csv(os.path.join(CONFIG["features_dir"], "baseline_results.csv"))
    log(f"\nsaved to {os.path.join(CONFIG['features_dir'], 'baseline_results.csv')}")


if __name__ == "__main__":
    main()
