#!/usr/bin/env python3
"""
Phase 2b - Build a PyG graph object from the sampled subgraph.

Converts the sampled edge tables (from sample_subgraph.py) into the structure
PyTorch Geometric needs for edge-level classification on a customer-product
bipartite graph:

  - customer nodes, each carrying the cust__* feature vector
  - product  nodes, each carrying the prod__* feature vector
  - edges = events, each carrying its keep/return label
  - a train edge mask and a test edge mask (so one graph holds both, and we
    train on train edges / evaluate on test edges)

We use PyG's HeteroData because customers and products are genuinely different
node types with different feature sets - matching the paper's bipartite framing.
Node features come straight from the Phase 1 feature columns (already imputed,
already scaled where needed), so no re-engineering: a customer node's features
are that customer's cust__* values, deduplicated to one row per customer.

Run:
    python build_graph.py /path/to/graph train
    python build_graph.py /path/to/graph train_test
"""

import os
import sys

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch_geometric.data import HeteroData

CONFIG = {
    "graph_dir": "./graph",
    "customer_key": "hash(customerId)",
    "product_key": "hash(variantID)",
    "label_col": "isReturned",
}


def log(msg=""):
    print(msg)


def node_feature_frame(edges_all, key, prefix):
    """One row of features per unique node id. Node features are constant per
    node in this dataset, so we take the first occurrence per id."""
    feat_cols = [c for c in edges_all.columns if c.startswith(prefix)]
    per_node = edges_all.drop_duplicates(subset=[key])[[key] + feat_cols]
    return per_node.reset_index(drop=True), feat_cols


def main():
    if len(sys.argv) > 1:
        CONFIG["graph_dir"] = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "train"

    ck, pk, lab = CONFIG["customer_key"], CONFIG["product_key"], CONFIG["label_col"]
    gdir = CONFIG["graph_dir"]

    log("=" * 70)
    log(f"PHASE 2b - BUILD PyG GRAPH  (mode={mode})")
    log("=" * 70)

    tr = pd.read_pickle(os.path.join(gdir, f"sub_{mode}_train.p"))
    te = pd.read_pickle(os.path.join(gdir, f"sub_{mode}_test.p"))
    tr["_is_test"] = 0
    te["_is_test"] = 1
    alle = pd.concat([tr, te], ignore_index=True)
    log(f"train edges {len(tr):,}, test edges {len(te):,}, total {len(alle):,}")

    # --- build the global node id maps across BOTH splits ---
    cust_feats_df, cust_cols = node_feature_frame(alle, ck, "cust__")
    prod_feats_df, prod_cols = node_feature_frame(alle, pk, "prod__")

    cust_ids = cust_feats_df[ck].to_numpy()
    prod_ids = prod_feats_df[pk].to_numpy()
    cust_index = {cid: i for i, cid in enumerate(cust_ids)}
    prod_index = {pid: i for i, pid in enumerate(prod_ids)}
    log(f"nodes: {len(cust_ids):,} customers ({len(cust_cols)} feats), "
        f"{len(prod_ids):,} products ({len(prod_cols)} feats)")

    # --- node feature tensors, STANDARDIZED (mean 0, std 1) ---
    # Neural nets (unlike the tree baselines) are very sensitive to feature
    # scale - raw values like avgGbpPrice up to ~518 or salesPerCustomer up to
    # ~3000 cause activations/gradients to explode. We fit the scaler only on
    # nodes that appear in TRAIN edges, to avoid leaking test-node statistics.
    train_edges = alle[alle["_is_test"] == 0]
    train_cust_ids = set(train_edges[ck].unique())
    train_prod_ids = set(train_edges[pk].unique())

    cust_train_rows = cust_feats_df[ck].isin(train_cust_ids).to_numpy()
    prod_train_rows = prod_feats_df[pk].isin(train_prod_ids).to_numpy()

    cust_scaler = StandardScaler().fit(cust_feats_df.loc[cust_train_rows, cust_cols].to_numpy(np.float32))
    prod_scaler = StandardScaler().fit(prod_feats_df.loc[prod_train_rows, prod_cols].to_numpy(np.float32))

    x_cust = torch.tensor(cust_scaler.transform(cust_feats_df[cust_cols].to_numpy(np.float32)), dtype=torch.float32)
    x_prod = torch.tensor(prod_scaler.transform(prod_feats_df[prod_cols].to_numpy(np.float32)), dtype=torch.float32)

    # --- edges (customer -> product), with labels and train/test masks ---
    src = alle[ck].map(cust_index).to_numpy()
    dst = alle[pk].map(prod_index).to_numpy()
    edge_index = torch.tensor(np.vstack([src, dst]), dtype=torch.long)
    edge_label = torch.tensor(alle[lab].to_numpy(np.float32))
    is_test = alle["_is_test"].to_numpy().astype(bool)
    train_mask = torch.tensor(~is_test)
    test_mask = torch.tensor(is_test)

    data = HeteroData()
    data["customer"].x = x_cust
    data["product"].x = x_prod
    data["customer", "buys", "product"].edge_index = edge_index
    data["customer", "buys", "product"].edge_label = edge_label
    data["customer", "buys", "product"].train_mask = train_mask
    data["customer", "buys", "product"].test_mask = test_mask
    # reverse relation so message passing updates BOTH node types (a bipartite
    # graph only has customer->product edges; without the reverse, product
    # nodes never receive messages and to_hetero() refuses to build).
    data["product", "rev_buys", "customer"].edge_index = edge_index.flip(0)

    # --- per-ORDER (edge) features: ord__* columns from build_features -------
    # These (COD flag, zone tier, courier, channel, promoCode) are known at
    # order time and present even for cold customers. Node message-passing can't
    # carry them, so we attach them directly to each edge and let the decoder
    # concatenate them with the learned node embeddings. Without this, the GNN
    # is blind to COD while the tabular baselines can see it - an unfair compare.
    ord_cols = sorted([c for c in alle.columns if c.startswith("ord__")])
    if ord_cols:
        edge_attr = torch.tensor(alle[ord_cols].to_numpy(np.float32), dtype=torch.float32)
        data["customer", "buys", "product"].edge_attr = edge_attr
        data["customer", "buys", "product"].edge_attr_names = ord_cols
        log(f"edge features: {len(ord_cols)} ord__ columns attached to edges")
    else:
        log("edge features: none found (no ord__ columns) - GNN runs node-only")

    # carry the cold-start flags + customer return rate through for evaluation
    for meta in ("customer_no_history", "product_no_history"):
        if meta in alle.columns:
            data["customer", "buys", "product"][meta] = torch.tensor(
                alle[meta].to_numpy(np.float32))
    rr_col = next((c for c in cust_cols if c.lower() == "cust__customerreturnrate"), None)
    if rr_col:
        data["customer", "buys", "product"]["cust_return_rate"] = torch.tensor(
            alle[rr_col].to_numpy(np.float32))

    out = os.path.join(gdir, f"graph_{mode}.pt")
    torch.save(data, out)
    log(f"\nsaved PyG graph to {out}")
    log(data)
    log("Next: train_gnn.py to train GraphSAGE on this graph.")


if __name__ == "__main__":
    main()
