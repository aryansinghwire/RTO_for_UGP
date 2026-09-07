#!/usr/bin/env python3
"""
Phase 2a - Connected Subgraph Sampler.

Takes the Phase 1 feature tables and carves out a SMALL, CONNECTED subgraph to
work with, instead of the full ~1.34M-event graph. Working at small scale is a
deliberate simplification (see the project plan): it lets the whole graph sit in
memory as one piece, so no partitioning is needed - which in turn means the
paper's Graph External Attention (GEA) module isn't required, since GEA exists
only to reconnect information across partitioned subgraphs.

The one thing that matters here: the sample must be CONNECTED. A naive random
sample of events would produce a shattered graph where almost no customer shares
a product with another - which defeats the purpose of a graph model (there'd be
no structure to learn from). So we grow the sample outward from a seed set of
products, following edges, so the pieces actually interlink.

Two modes:
  - "train"      : sample only from the training-period events. Every node is
                   warm (seen during training). Used to prove the pipeline works.
  - "train_test" : sample a connected subgraph, then keep the natural split -
                   train edges come from the training period, test edges from the
                   testing period. Cold-start customers (in test, absent from
                   train) are preserved, so this tests the real deployment case.

Run:
    python sample_subgraph.py /path/to/features /path/to/graph_out train 40000
    python sample_subgraph.py /path/to/features /path/to/graph_out train_test 40000
"""

import os
import sys

import numpy as np
import pandas as pd

CONFIG = {
    "features_dir": "./features",
    "out_dir": "./graph",
    "customer_key": "hash(customerId)",
    "product_key": "hash(variantID)",
    "label_col": "isReturned",
    "seed": 42,
    # sampling grows from the most-connected products so the subgraph is dense
    # enough to be a meaningful graph rather than a scatter of tiny components.
    "n_seed_products": 400,
}


def log(msg=""):
    print(msg)


def load_features(features_dir, name):
    return pd.read_pickle(os.path.join(features_dir, f"{name}_features.p"))


def grow_connected_sample(events, cfg, target_events, seed_pool_events=None):
    """
    Grow a connected edge sample. Start from a seed set of high-degree products,
    take all their events, collect the customers touched, take those customers'
    other events too, and repeat until we reach ~target_events. This
    breadth-first growth keeps the sample connected instead of scattered.

    `seed_pool_events` (optional) is the event set used to CHOOSE seed products
    (e.g. train events), while `events` is the pool we actually pull edges from.
    For train-only they're the same; for train+test they differ.
    """
    ck, pk = cfg["customer_key"], cfg["product_key"]
    rng = np.random.RandomState(cfg["seed"])
    pool = events if seed_pool_events is None else seed_pool_events

    # pick seed products: the most-connected ones, for a dense core
    prod_degree = pool[pk].value_counts()
    top_products = prod_degree.head(cfg["n_seed_products"] * 5).index.to_numpy()
    seed_products = set(rng.choice(top_products,
                                   size=min(cfg["n_seed_products"], len(top_products)),
                                   replace=False))

    chosen_products = set(seed_products)
    chosen_customers = set()
    frontier_products = set(seed_products)

    while True:
        # edges touching current product frontier
        mask = events[pk].isin(frontier_products)
        new_customers = set(events.loc[mask, ck].unique()) - chosen_customers
        chosen_customers |= new_customers
        if not new_customers:
            break

        # edges from those new customers pull in more products
        cmask = events[ck].isin(new_customers)
        # NOTE: this must match the AND used to build `sub` below, not OR. An OR
        # count is inflated by every other order a newly-found customer happens
        # to have (regardless of product), so at higher density it can look like
        # the target is reached while chosen_products is still stuck at the seed
        # set - the loop stops before ever growing past the seeds, and the AND-
        # filtered `sub` ends up far smaller than target with product count
        # exactly == n_seed_products. Using AND here keeps the stop condition
        # honest about what will actually be kept.
        current_edges = int(events[events[pk].isin(chosen_products)
                                   & events[ck].isin(chosen_customers)].shape[0])
        if current_edges >= target_events:
            break

        new_products = set(events.loc[cmask, pk].unique()) - chosen_products
        chosen_products |= new_products
        frontier_products = new_products
        if not new_products:
            break

    sub = events[events[pk].isin(chosen_products) & events[ck].isin(chosen_customers)]
    return sub.reset_index(drop=True)


def summarize(sub, cfg, label):
    ck, pk, lab = cfg["customer_key"], cfg["product_key"], cfg["label_col"]
    log(f"  {label}: {len(sub):,} edges, "
        f"{sub[ck].nunique():,} customers, {sub[pk].nunique():,} products, "
        f"return rate {sub[lab].mean():.3f}")


def main():
    if len(sys.argv) > 1:
        CONFIG["features_dir"] = sys.argv[1]
    if len(sys.argv) > 2:
        CONFIG["out_dir"] = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "train"
    target = int(sys.argv[4]) if len(sys.argv) > 4 else 40000

    os.makedirs(CONFIG["out_dir"], exist_ok=True)
    log("=" * 70)
    log(f"PHASE 2a - SUBGRAPH SAMPLER  (mode={mode}, target~{target:,} train edges)")
    log("=" * 70)

    ck, pk = CONFIG["customer_key"], CONFIG["product_key"]

    if mode == "train":
        train = load_features(CONFIG["features_dir"], "train")
        log(f"loaded train features: {train.shape}")
        sub = grow_connected_sample(train, CONFIG, target)
        summarize(sub, CONFIG, "sampled subgraph")

        # within-graph split: hold out 20% of edges for testing
        rng = np.random.RandomState(CONFIG["seed"])
        perm = rng.permutation(len(sub))
        n_test = int(len(sub) * 0.2)
        test_idx, train_idx = perm[:n_test], perm[n_test:]
        sub_train = sub.iloc[train_idx].reset_index(drop=True)
        sub_test = sub.iloc[test_idx].reset_index(drop=True)
        summarize(sub_train, CONFIG, "  -> train split")
        summarize(sub_test, CONFIG, "  -> test  split")

    elif mode == "train_test":
        train = load_features(CONFIG["features_dir"], "train")
        test = load_features(CONFIG["features_dir"], "test")
        log(f"loaded train {train.shape}, test {test.shape}")

        # grow a connected sample over the COMBINED edge set, seeding from train
        combined = pd.concat([train.assign(_split="train"),
                              test.assign(_split="test")], ignore_index=True)
        sub = grow_connected_sample(combined, CONFIG, target, seed_pool_events=train)
        sub_train = sub[sub["_split"] == "train"].drop(columns="_split").reset_index(drop=True)
        sub_test = sub[sub["_split"] == "test"].drop(columns="_split").reset_index(drop=True)

        summarize(sub, CONFIG, "sampled subgraph (combined)")
        summarize(sub_train, CONFIG, "  -> train edges (Sep-Oct)")
        summarize(sub_test, CONFIG, "  -> test  edges (Oct-Nov)")

        # cold-start report: test customers/products absent from the train portion
        tr_cust, tr_prod = set(sub_train[ck]), set(sub_train[pk])
        te_cust, te_prod = set(sub_test[ck]), set(sub_test[pk])
        cold_c = len(te_cust - tr_cust)
        cold_p = len(te_prod - tr_prod)
        log(f"  cold-start in subgraph: "
            f"{cold_c:,}/{len(te_cust):,} test customers unseen "
            f"({100*cold_c/max(len(te_cust),1):.1f}%), "
            f"{cold_p:,}/{len(te_prod):,} test products unseen "
            f"({100*cold_p/max(len(te_prod),1):.1f}%)")
    else:
        log(f"unknown mode '{mode}' - use 'train' or 'train_test'")
        return

    sub_train.to_pickle(os.path.join(CONFIG["out_dir"], f"sub_{mode}_train.p"))
    sub_test.to_pickle(os.path.join(CONFIG["out_dir"], f"sub_{mode}_test.p"))
    log(f"\nwrote sub_{mode}_train.p and sub_{mode}_test.p to {CONFIG['out_dir']}")
    log("Next: build_graph.py to convert these into a PyG graph object.")


if __name__ == "__main__":
    main()