#!/usr/bin/env python3
"""
Phase 0 - Data Profiler for the Returnformer / RTO Risk Engine build.

Loads the six supplied pickle tables (event / customer / product x train / test),
checks them against the schema in PRD Section 7, verifies the graph join keys
resolve, and reports the distributions you need before writing any model code.

Run:
    python profile_data.py                 # uses CONFIG['data_dir'] below
    python profile_data.py /path/to/folder # or pass the folder as an argument

Output:
    - a sectioned report printed to the console
    - a markdown summary written to data_profile_report.md

Only needs pandas + numpy. Written to run on pandas >= 1.3 (nothing exotic).
"""

import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 60)

# --------------------------------------------------------------------------- #
# CONFIG - edit this block to point at your data.                             #
# --------------------------------------------------------------------------- #
CONFIG = {
    # Folder holding the six .p files. Override by passing a path on the CLI.
    "data_dir": ".",
    "files": {
        "event_train":    "event_table_training.p",
        "event_test":     "event_table_testing.p",
        "customer_train": "customer_nodes_training.p",
        "customer_test":  "customer_nodes_testing.p",
        "product_train":  "product_nodes_training.p",
        "product_test":   "product_nodes_testing.p",
    },
    # Leave as None to auto-detect. Set explicitly (a column name string) only
    # if auto-detection guesses wrong - the report tells you what it picked.
    "label_col": None,          # binary target in the event table (isReturned)
    "event_customer_key": None, # customer-id column IN the event table
    "event_product_key": None,  # variant-id column IN the event table
    "customer_key": None,       # customer-id column IN the customer node table
    "product_key": None,        # variant-id column IN the product node table
    # Paper-reported figures, used only as a sanity reference (not asserted).
    "paper_reference": {
        "event_train_rows": 939537,
        "event_test_rows": 858526,
        "unique_users": 1084504,
        "unique_variants": 338076,
        "pos_neg_ratio": 1.2,  # return : keep
    },
}

SECTION = "=" * 78
SUB = "-" * 78
_report_lines = []  # collected for the markdown file
_dupe_info = {}     # {table_name: [(original_name, renamed_to), ...]}


def log(msg=""):
    print(msg)
    _report_lines.append(str(msg))


def section(title):
    log("\n" + SECTION)
    log(title)
    log(SECTION)


def safe(fn, *args, **kwargs):
    """Run an analysis section; if it errors, log it and continue so the rest
    of the report (and the saved markdown) is still produced."""
    try:
        fn(*args, **kwargs)
    except Exception as e:
        log(f"\n  [section '{fn.__name__}' errored: {type(e).__name__}: {e}]")
        log("  [skipped - the rest of the report below is still valid]")


# --------------------------------------------------------------------------- #
# Loading                                                                     #
# --------------------------------------------------------------------------- #
def dedupe_columns(name, df):
    """Rename any duplicate column names in place (no full copy) so every
    df[col] returns a Series, not a DataFrame. Records what was renamed."""
    seen, new, dups = {}, [], []
    for c in df.columns:
        if c in seen:
            seen[c] += 1
            renamed = f"{c}.dup{seen[c]}"
            new.append(renamed)
            dups.append((c, renamed))
        else:
            seen[c] = 0
            new.append(c)
    if dups:
        df.columns = new          # assigns labels only - does not copy data
        _dupe_info[name] = dups
    return df


def load_all(data_dir, files):
    dfs = {}
    section("1. FILE LOADING")
    for name, fname in files.items():
        path = os.path.join(data_dir, fname)
        if not os.path.exists(path):
            log(f"  [MISSING]  {name:16s} -> {path}")
            dfs[name] = None
            continue
        try:
            df = pd.read_pickle(path)
            df = dedupe_columns(name, df)
            size_mb = os.path.getsize(path) / 1e6
            log(f"  [OK]       {name:16s} -> {fname}  "
                f"({df.shape[0]:,} rows x {df.shape[1]} cols, {size_mb:.1f} MB)")
            dfs[name] = df
        except Exception as e:
            log(f"  [ERROR]    {name:16s} -> {fname}: {type(e).__name__}: {e}")
            dfs[name] = None
    return dfs


def duplicate_column_report(dfs):
    if not _dupe_info:
        return
    section("2b. DUPLICATE COLUMN NAMES  (resolve before Phase 1)")
    for name, dups in _dupe_info.items():
        for orig, renamed in dups:
            log(f"  {name}: '{orig}' appeared more than once "
                f"-> duplicate renamed to '{renamed}' for profiling")
    log("\n  Two columns share a name but hold DIFFERENT data. Decide which is the")
    log("  real column (or whether one is mislabeled) before building features -")
    log("  a duplicated reason-code column would double-count in any row-sum.")


# --------------------------------------------------------------------------- #
# Schema auto-detection                                                        #
# --------------------------------------------------------------------------- #
def find_col(df, candidates):
    """Return the first column whose lowercased name contains any candidate."""
    if df is None:
        return None
    lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        for lc, orig in lower.items():
            if cand in lc:
                return orig
    return None


def detect_binary_label(df):
    """Find a 0/1 column - prefer one named like isReturned/isRTO."""
    if df is None:
        return None
    named = find_col(df, ["isreturned", "isrto", "returned", "label", "target"])
    if named is not None:
        return named
    # otherwise: any column with exactly {0,1} values
    for c in df.columns:
        vals = pd.unique(df[c].dropna())
        if len(vals) <= 2 and set(np.array(vals).astype(str)) <= {"0", "1", "0.0", "1.0"}:
            return c
    return None


def detect_key_by_overlap(event_df, node_df, node_key):
    """Pick the event-table column whose values best overlap the node key."""
    if event_df is None or node_df is None or node_key is None:
        return None
    node_vals = set(node_df[node_key].unique())
    best_col, best_frac = None, -1.0
    for c in event_df.columns:
        try:
            ev_vals = set(event_df[c].dropna().unique())
        except TypeError:
            continue
        if not ev_vals:
            continue
        frac = len(ev_vals & node_vals) / len(ev_vals)
        if frac > best_frac:
            best_col, best_frac = c, frac
    return best_col if best_frac > 0.5 else None


def resolve_schema(dfs, cfg):
    section("2. SCHEMA DETECTION")
    ev = dfs.get("event_train")
    cust = dfs.get("customer_train")
    prod = dfs.get("product_train")

    label = cfg["label_col"] or detect_binary_label(ev)
    cust_key = cfg["customer_key"] or find_col(cust, ["customerid", "customer", "hash(customer"])
    prod_key = cfg["product_key"] or find_col(prod, ["variantid", "variant", "hash(variant"])

    ev_cust = cfg["event_customer_key"] or find_col(ev, ["customerid", "customer"])
    ev_prod = cfg["event_product_key"] or find_col(ev, ["variantid", "variant"])
    # fall back to value-overlap if name matching failed
    if ev_cust is None:
        ev_cust = detect_key_by_overlap(ev, cust, cust_key)
    if ev_prod is None:
        ev_prod = detect_key_by_overlap(ev, prod, prod_key)

    schema = {
        "label": label,
        "customer_key": cust_key,
        "product_key": prod_key,
        "event_customer_key": ev_cust,
        "event_product_key": ev_prod,
    }
    for k, v in schema.items():
        status = "OK" if v is not None else "NOT FOUND - set manually in CONFIG"
        log(f"  {k:22s}: {str(v):30s} [{status}]")
    return schema


# --------------------------------------------------------------------------- #
# Per-table profile                                                            #
# --------------------------------------------------------------------------- #
def group_prefixes(cols):
    """Summarise wide one-hot / reason-code column families by prefix count."""
    fams = {}
    for c in cols:
        # strip a trailing _X / _A style suffix to find the family stem
        stem = c.rsplit("_", 1)[0] if "_" in c else c
        fams.setdefault(stem, 0)
        fams[stem] += 1
    return {k: v for k, v in fams.items() if v >= 3}


def profile_table(name, df, expected_cols=None):
    section(f"3. TABLE PROFILE - {name}")
    if df is None:
        log("  (not loaded - skipped)")
        return
    log(f"  shape: {df.shape[0]:,} rows x {df.shape[1]} cols")
    log(f"  memory: {df.memory_usage(deep=True).sum() / 1e6:.1f} MB in RAM")

    if expected_cols is not None:
        log(f"  expected column count (PRD): {expected_cols}  |  actual: {df.shape[1]}")

    # dtypes summary
    log("\n  dtypes:")
    for dt, cnt in df.dtypes.value_counts().items():
        log(f"    {str(dt):12s}: {cnt} cols")

    # wide column families (reason codes, one-hots)
    fams = group_prefixes(df.columns)
    if fams:
        log("\n  wide column families (>=3 cols sharing a stem):")
        for stem, cnt in sorted(fams.items(), key=lambda x: -x[1]):
            log(f"    {stem + '_*':40s}: {cnt} columns")

    # missing values
    miss = df.isna().sum()
    miss = miss[miss > 0].sort_values(ascending=False)
    log("\n  missing values:")
    if len(miss) == 0:
        log("    none")
    else:
        for c, n in miss.head(20).items():
            log(f"    {c:40s}: {n:,} ({100 * n / len(df):.2f}%)")
        if len(miss) > 20:
            log(f"    ... and {len(miss) - 20} more columns with missing values")

    # numeric summary (cap columns shown)
    num = df.select_dtypes(include=[np.number])
    if num.shape[1] > 0:
        show = [c for c in num.columns if group_prefixes([c]) == {}][:12]
        if show:
            log("\n  numeric summary (non-family columns, up to 12):")
            desc = num[show].describe().T[["mean", "std", "min", "50%", "max"]]
            for line in desc.round(3).to_string().splitlines():
                log("    " + line)

    # low-cardinality categoricals (positional access = always a Series)
    log("\n  low-cardinality columns (<=10 uniques):")
    shown, seen_names = 0, set()
    for i, c in enumerate(df.columns):
        if c in seen_names:
            continue
        seen_names.add(c)
        col = df.iloc[:, i]
        nun = int(col.nunique(dropna=True))
        if nun <= 10 and shown < 8:
            vc = col.value_counts(dropna=False).head(6)
            pretty = ", ".join(f"{idx}:{cnt:,}" for idx, cnt in vc.items())
            log(f"    {c:32s} ({nun} uniq): {pretty}")
            shown += 1
    if shown == 0:
        log("    none")


# --------------------------------------------------------------------------- #
# Label balance                                                                #
# --------------------------------------------------------------------------- #
def label_balance(dfs, schema, cfg):
    section("4. LABEL BALANCE (isReturned)")
    label = schema["label"]
    if label is None:
        log("  label column not identified - skipped")
        return
    for split in ("event_train", "event_test"):
        df = dfs.get(split)
        if df is None or label not in df.columns:
            log(f"  {split}: unavailable")
            continue
        vc = df[label].value_counts(dropna=False)
        pos = int(vc.get(1, vc.get(1.0, 0)))
        neg = int(vc.get(0, vc.get(0.0, 0)))
        total = pos + neg
        if total == 0:
            log(f"  {split}: no 0/1 values found in '{label}'")
            continue
        ratio = pos / neg if neg else float("inf")
        log(f"  {split}: returned(1)={pos:,}  kept(0)={neg:,}  "
            f"pos:neg = {ratio:.2f}:1  (positive share {100 * pos / total:.1f}%)")
    ref = cfg["paper_reference"]["pos_neg_ratio"]
    log(f"\n  paper reference pos:neg ratio ~= {ref}:1 (for sanity comparison only)")


# --------------------------------------------------------------------------- #
# Join-key integrity - the load-bearing check                                  #
# --------------------------------------------------------------------------- #
def join_integrity(dfs, schema):
    section("5. GRAPH JOIN-KEY INTEGRITY  (critical)")
    checks = [
        ("customer", "event_train", "customer_train", "event_customer_key", "customer_key"),
        ("customer", "event_test",  "customer_test",  "event_customer_key", "customer_key"),
        ("product",  "event_train", "product_train",  "event_product_key",  "product_key"),
        ("product",  "event_test",  "product_test",   "event_product_key",  "product_key"),
    ]
    for kind, ev_name, node_name, ev_key_name, node_key_name in checks:
        ev = dfs.get(ev_name)
        node = dfs.get(node_name)
        ev_key = schema.get(ev_key_name)
        node_key = schema.get(node_key_name)
        if ev is None or node is None or ev_key is None or node_key is None:
            log(f"  {ev_name} -> {node_name} [{kind}]: skipped (missing table or key)")
            continue

        ev_ids = ev[ev_key]
        node_ids = set(node[node_key].unique())
        resolved = ev_ids.isin(node_ids)
        n_orphan = int((~resolved).sum())
        pct_orphan = 100 * n_orphan / len(ev_ids) if len(ev_ids) else 0

        dup = int(node[node_key].duplicated().sum())
        flag = "  <-- ORPHANS PRESENT" if n_orphan else ""
        log(f"  {ev_name:13s} -> {node_name:16s} [{kind}]: "
            f"{n_orphan:,} unresolved edges ({pct_orphan:.2f}%){flag}")
        if dup:
            log(f"      WARNING: {dup:,} duplicate '{node_key}' keys in {node_name} "
                f"- node table is not unique on its key")
    log("\n  (Every edge endpoint should resolve to a node row. Non-zero orphan")
    log("   rates mean edges that reference a customer/product with no feature row.)")


# --------------------------------------------------------------------------- #
# Train/test overlap - the cold-start signal                                   #
# --------------------------------------------------------------------------- #
def cold_start_overlap(dfs, schema):
    section("6. TRAIN/TEST ENTITY OVERLAP  (cold-start signal)")
    pairs = [
        ("customers", "customer_train", "customer_test", "customer_key"),
        ("products",  "product_train",  "product_test",  "product_key"),
    ]
    for label, train_name, test_name, key_name in pairs:
        tr = dfs.get(train_name)
        te = dfs.get(test_name)
        key = schema.get(key_name)
        if tr is None or te is None or key is None:
            log(f"  {label}: skipped (missing table or key)")
            continue
        tr_ids = set(tr[key].unique())
        te_ids = set(te[key].unique())
        unseen = te_ids - tr_ids
        pct = 100 * len(unseen) / len(te_ids) if te_ids else 0
        log(f"  {label}: {len(tr_ids):,} in train, {len(te_ids):,} in test, "
            f"{len(unseen):,} test-only ({pct:.1f}% cold-start)")
    log("\n  (Test entities absent from train have no graph history -> these are the")
    log("   orders the baseline fallback model must score. This % sizes that need.)")


# --------------------------------------------------------------------------- #
# Reason-code sanity (proportions should sum to ~1 per row)                     #
# --------------------------------------------------------------------------- #
def reason_code_sanity(dfs):
    section("7. RETURN-REASON PROFILE SANITY")
    for name in ("customer_train", "product_train"):
        df = dfs.get(name)
        if df is None:
            continue
        fams = group_prefixes(df.columns)
        # a reason-code family = a numeric family with values in [0,1]
        cand, chosen_sub = None, None
        for stem, cnt in fams.items():
            fam_cols = [c for c in df.columns if c.rsplit("_", 1)[0] == stem]
            sub = df[fam_cols].select_dtypes(include=[np.number])
            sub = sub.loc[:, ~sub.columns.duplicated()]  # avoid double-count
            if sub.shape[1] >= 5 and float(np.nanmax(sub.to_numpy())) <= 1.5:
                cand, chosen_sub = (stem, list(sub.columns)), sub
                break
        if cand is None:
            log(f"  {name}: no obvious reason-code proportion family detected")
            continue
        stem, num_cols = cand
        rowsum = chosen_sub.sum(axis=1)
        log(f"  {name}: family '{stem}_*' ({len(num_cols)} numeric cols) "
            f"row-sum mean={rowsum.mean():.3f}, "
            f"share of rows summing ~1.0 = "
            f"{100 * ((rowsum > 0.95) & (rowsum < 1.05)).mean():.1f}%")
    log("\n  (Reason-code columns are proportions of a customer's/product's past")
    log("   returns; rows should sum to ~1 where any returns exist.)")


# --------------------------------------------------------------------------- #
# Reference comparison                                                         #
# --------------------------------------------------------------------------- #
def reference_check(dfs, cfg, schema):
    section("8. SANITY vs PAPER-REPORTED SCALE")
    ref = cfg["paper_reference"]
    ev_tr = dfs.get("event_train")
    ev_te = dfs.get("event_test")
    if ev_tr is not None:
        log(f"  event_train rows: {len(ev_tr):,}  (paper: {ref['event_train_rows']:,})")
    if ev_te is not None:
        log(f"  event_test  rows: {len(ev_te):,}  (paper: {ref['event_test_rows']:,})")
    ck = schema.get("customer_key")
    pk = schema.get("product_key")
    users = set()
    variants = set()
    for n in ("customer_train", "customer_test"):
        if dfs.get(n) is not None and ck:
            users |= set(dfs[n][ck].unique())
    for n in ("product_train", "product_test"):
        if dfs.get(n) is not None and pk:
            variants |= set(dfs[n][pk].unique())
    if users:
        log(f"  unique customers (train+test): {len(users):,}  (paper: {ref['unique_users']:,})")
    if variants:
        log(f"  unique variants  (train+test): {len(variants):,}  (paper: {ref['unique_variants']:,})")
    log("\n  (Small deviations are fine - the paper's counts are post-cleaning.")
    log("   Large gaps mean a different export or an extra preprocessing step.)")


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #
def main():
    if len(sys.argv) > 1:
        CONFIG["data_dir"] = sys.argv[1]

    log(SECTION)
    log("PHASE 0 DATA PROFILE  -  Returnformer / RTO Risk Engine")
    log(f"data_dir: {os.path.abspath(CONFIG['data_dir'])}")
    log(SECTION)

    dfs = load_all(CONFIG["data_dir"], CONFIG["files"])
    if all(v is None for v in dfs.values()):
        log("\nNo files loaded. Edit CONFIG['data_dir'] or pass a folder path. Stopping.")
        _flush_report()
        return

    duplicate_column_report(dfs)
    schema = resolve_schema(dfs, CONFIG)

    # PRD Section 7 expected column counts (soft reference)
    expected = {
        "event_train": 3, "event_test": 3,
        "customer_train": 30, "customer_test": 30,
        "product_train": 44, "product_test": 44,
    }
    try:
        for name in ("event_train", "customer_train", "product_train"):
            safe(profile_table, name, dfs.get(name), expected.get(name))

        safe(label_balance, dfs, schema, CONFIG)
        safe(join_integrity, dfs, schema)
        safe(cold_start_overlap, dfs, schema)
        safe(reason_code_sanity, dfs)
        safe(reference_check, dfs, CONFIG, schema)

        section("DONE")
        log("  Review the join-integrity and cold-start sections first - they gate")
        log("  Phase 1. If both look clean, you're clear to build the baseline.")
    finally:
        _flush_report()  # always save the report, even if a section errored


def _flush_report():
    out = "data_profile_report.md"
    try:
        with open(out, "w") as f:
            f.write("# Phase 0 Data Profile Report\n\n```\n")
            f.write("\n".join(_report_lines))
            f.write("\n```\n")
        print(f"\n[report written to {os.path.abspath(out)}]")
    except Exception as e:
        print(f"\n[could not write report: {e}]")


if __name__ == "__main__":
    main()