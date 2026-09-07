#!/usr/bin/env python3
"""
Phase 1 - Feature Build for the Returnformer / RTO Risk Engine baseline.

Takes the CLEANED six pickle tables (output of clean_data.py) and produces one
row per event: the event's label plus its customer- and product-side features,
joined in. This is the flat table the four tabular baselines (Section 4.2 of
the paper / PRD Section 9) train on.

Handles the two structural realities the profiler surfaced:
  - ~5% customer-side and ~31-35% product-side edges are ORPHANS (no node row).
    These are imputed, not dropped - an orphan is a real cold-start order, and
    the PRD requires cold-start orders to be scored, not skipped.
  - ~78% of test customers are unseen in train (cold-start). A `_no_history`
    flag is added for both customer and product sides so models can learn to
    treat imputed rows differently from real history.

Imputation policy (by column role, detected by name pattern):
  - RATE columns (*ReturnRate)              -> mean-filled from that split's
                                                 own node table (a plausible
                                                 population default)
  - COUNT / reason-code-proportion columns   -> zero-filled (no history = 0)
    (salesPer*, returnsPer*, *_return_code_*)
  - CONTINUOUS descriptive columns            -> mean-filled (0 isn't
    (age, avgGbpPrice, avgDiscountValue)        plausible for these)
  - BINARY / one-hot columns (Country_*,     -> zero-filled ("unknown
    Brand_*, productType_*, isMale, premier)     category" = no flag set)
  - raw text columns (e.g. shippingCountry)  -> dropped (one-hots already
                                                 carry this information)

Run:
    python build_features.py /path/to/clean /path/to/features_out
"""

import os
import sys

import numpy as np
import pandas as pd

CONFIG = {
    "clean_dir": ".",
    "out_dir": "./features",
    "files": {
        "event_train":    "event_table_training.p",
        "event_test":     "event_table_testing.p",
        "customer_train": "customer_nodes_training.p",
        "customer_test":  "customer_nodes_testing.p",
        "product_train":  "product_nodes_training.p",
        "product_test":   "product_nodes_testing.p",
    },
    "customer_key": "hash(customerId)",
    "product_key": "hash(variantID)",
    "label_col": "isReturned",
    # --- India order-level (edge) features ---------------------------------
    # If this side file is present (written by india_synth_generator.py), its
    # per-ORDER fields are folded in as `ord__*` features. Unlike node features,
    # these are known at order time and are present even for cold customers -
    # which is exactly the slice the node-history features can't help. The base
    # event tables carry no such fields, so on ASOS data this simply no-ops.
    "india_extra_file": "event_india_extra.p",
    "use_india_order_features": True,
    # categorical order fields -> one-hot; binary/count fields kept as-is
    "order_cat_cols": ["deliveryZoneTier", "courierPartner", "orderChannel"],
    "order_binary_cols": ["promoCode"],
    "order_cod_col": "paymentMethod",   # -> ord__is_cod (COD=1)
    # deliberately EXCLUDED: deliveryAttemptCount (leaks the label - it's
    # 1 + isRTO*rand, so >1 reveals the outcome; also a post-dispatch field),
    # promisedDeliveryDate (a date; its signal is just tier, already captured),
    # _is_test (internal split flag, used only to split then dropped).
    "rate_patterns": ["returnrate"],
    "count_patterns": ["salesper", "returnsper", "level_return_code", "_return_code_"],
    "continuous_patterns": ["age", "avggbpprice", "avgdiscountvalue"],
    # everything else numeric falls back to zero-fill (treated as one-hot/binary)
}


def log(msg=""):
    print(msg)


def classify_columns(cols, cfg):
    """Bucket feature columns by imputation rule, via substring match on the
    lowercased name. Returns dict: rule_name -> [columns]."""
    rate, count, cont, other = [], [], [], []
    for c in cols:
        lc = c.lower()
        if any(p in lc for p in cfg["rate_patterns"]):
            rate.append(c)
        elif any(p in lc for p in cfg["count_patterns"]):
            count.append(c)
        elif any(p in lc for p in cfg["continuous_patterns"]):
            cont.append(c)
        else:
            other.append(c)
    return {"rate": rate, "count": count, "continuous": cont, "binary_other": other}


def prep_node_table(df, key_col, cfg, table_label):
    """Drop the key from the feature set, drop non-numeric columns (logged),
    and return (numeric_feature_df_with_key, impute_values_dict)."""
    obj_cols = [c for c in df.columns if df[c].dtype == "object" and c != key_col]
    if obj_cols:
        log(f"  {table_label}: dropping non-numeric column(s) {obj_cols} "
            f"(one-hot equivalents are kept)")
    feat_cols = [c for c in df.columns
                 if c != key_col and c not in obj_cols
                 and pd.api.types.is_numeric_dtype(df[c])]
    df_num = df[[key_col] + feat_cols].copy()

    buckets = classify_columns(feat_cols, cfg)
    impute = {}
    for c in buckets["rate"] + buckets["continuous"]:
        impute[c] = float(df_num[c].mean())
    for c in buckets["count"] + buckets["binary_other"]:
        impute[c] = 0.0

    log(f"  {table_label}: {len(feat_cols)} numeric features "
        f"(rate={len(buckets['rate'])}, count/reason={len(buckets['count'])}, "
        f"continuous={len(buckets['continuous'])}, binary/other={len(buckets['binary_other'])})")
    return df_num, feat_cols, impute


def build_split(event_df, cust_df, prod_df, cfg, split_name):
    ck, pk, label = cfg["customer_key"], cfg["product_key"], cfg["label_col"]

    log(f"\n--- building {split_name} ---")
    cust_num, cust_feats, cust_impute = prep_node_table(cust_df, ck, cfg, "customer")
    prod_num, prod_feats, prod_impute = prep_node_table(prod_df, pk, cfg, "product")

    # prefix feature columns so customer/product namespaces never collide
    cust_num = cust_num.rename(columns={c: f"cust__{c}" for c in cust_feats})
    prod_num = prod_num.rename(columns={c: f"prod__{c}" for c in prod_feats})
    cust_impute = {f"cust__{k}": v for k, v in cust_impute.items()}
    prod_impute = {f"prod__{k}": v for k, v in prod_impute.items()}

    df = event_df.merge(cust_num, on=ck, how="left")
    df = df.merge(prod_num, on=pk, how="left")

    cust_cols = list(cust_impute.keys())
    prod_cols = list(prod_impute.keys())

    df["customer_no_history"] = df[cust_cols[0]].isna().astype(np.int8) if cust_cols else 0
    df["product_no_history"] = df[prod_cols[0]].isna().astype(np.int8) if prod_cols else 0

    n_cust_orphan = int(df["customer_no_history"].sum())
    n_prod_orphan = int(df["product_no_history"].sum())
    log(f"  imputed {n_cust_orphan:,} customer-side orphans "
        f"({100 * n_cust_orphan / len(df):.2f}%), "
        f"{n_prod_orphan:,} product-side orphans "
        f"({100 * n_prod_orphan / len(df):.2f}%)")

    df = df.fillna({**cust_impute, **prod_impute})

    # compact dtypes - halves memory vs default float64
    num_cols = cust_cols + prod_cols
    df[num_cols] = df[num_cols].astype(np.float32)

    log(f"  final shape: {df.shape[0]:,} rows x {df.shape[1]} cols "
        f"({df.memory_usage(deep=True).sum() / 1e6:.1f} MB)")
    return df


def load_india_order_features(clean_dir, cfg):
    """If the India side file is present, return (ev_train, ev_test) event
    frames enriched with `ord__*` per-order features. One-hot categories are
    fit on BOTH splits together, then split, so train/test share identical
    columns. Returns None if the file is absent (e.g. on ASOS data)."""
    if not cfg.get("use_india_order_features"):
        return None
    path = os.path.join(clean_dir, cfg["india_extra_file"])
    if not os.path.exists(path):
        return None

    raw = pd.read_pickle(path)
    ck, pk, label = cfg["customer_key"], cfg["product_key"], cfg["label_col"]
    keep_ids = [pk, ck, label]

    df = raw[keep_ids].copy()

    # COD flag
    cod_col = cfg["order_cod_col"]
    if cod_col in raw.columns:
        df["ord__is_cod"] = (raw[cod_col].astype(str).str.upper() == "COD").astype(np.int8)

    # binary/count fields carried straight through
    for c in cfg["order_binary_cols"]:
        if c in raw.columns:
            df[f"ord__{c}"] = pd.to_numeric(raw[c], errors="coerce").fillna(0).astype(np.int8)

    # one-hot the categoricals (fit on all rows -> aligned columns across splits)
    for c in cfg["order_cat_cols"]:
        if c in raw.columns:
            dummies = pd.get_dummies(raw[c].astype(str), prefix=f"ord__{c}").astype(np.int8)
            df = pd.concat([df, dummies], axis=1)

    ord_cols = [c for c in df.columns if c.startswith("ord__")]

    # split back using the internal flag, then drop it
    is_test = raw["_is_test"].to_numpy().astype(bool)
    ev_train = df.loc[~is_test].reset_index(drop=True)
    ev_test = df.loc[is_test].reset_index(drop=True)

    log(f"  India order features: {len(ord_cols)} ord__ columns "
        f"({', '.join(ord_cols)})")
    log(f"    train rows {len(ev_train):,}, test rows {len(ev_test):,} "
        f"(present for ALL orders, including cold-start)")
    return ev_train, ev_test


def main():
    if len(sys.argv) > 1:
        CONFIG["clean_dir"] = sys.argv[1]
    if len(sys.argv) > 2:
        CONFIG["out_dir"] = sys.argv[2]

    clean, out = CONFIG["clean_dir"], CONFIG["out_dir"]
    os.makedirs(out, exist_ok=True)
    log("=" * 70)
    log("PHASE 1 - FEATURE BUILD")
    log(f"clean: {os.path.abspath(clean)}")
    log(f"out  : {os.path.abspath(out)}")
    log("=" * 70)

    def load(name):
        return pd.read_pickle(os.path.join(clean, CONFIG["files"][name]))

    india = load_india_order_features(clean, CONFIG)
    if india is not None:
        ev_tr, ev_te = india
        log("  using enriched India event tables (base 3-col tables ignored)")
    else:
        ev_tr, ev_te = load("event_train"), load("event_test")
    cust_tr, cust_te = load("customer_train"), load("customer_test")
    prod_tr, prod_te = load("product_train"), load("product_test")

    train_feats = build_split(ev_tr, cust_tr, prod_tr, CONFIG, "train")
    test_feats = build_split(ev_te, cust_te, prod_te, CONFIG, "test")

    train_feats.to_pickle(os.path.join(out, "train_features.p"))
    test_feats.to_pickle(os.path.join(out, "test_features.p"))

    log("\n" + "=" * 70)
    log("DONE. Feature tables written to the output folder.")
    log("Next: run train_baselines.py against this folder.")
    log("=" * 70)


if __name__ == "__main__":
    main()