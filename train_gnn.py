#!/usr/bin/env python3
"""
Phase 2c - GraphSAGE baseline on the bipartite graph.

The first GRAPH model. GraphSAGE is deliberately the simple stepping-stone (one
built-in PyG layer, not written from scratch). Its job is only to (1) prove the
graph is wired correctly end to end, and (2) give a first graph-based number to
compare against the Phase 1 tabular baseline. This is NOT the Returnformer -
that's Phase 3.

Architecture:
  - two SAGEConv layers over the bipartite (customer<->product) graph, run in
    both directions so both node types get updated (PyG's to_hetero handles this)
  - for each event-edge, concatenate its customer and product embeddings and
    pass through a small MLP to predict return probability (edge-level task)

Evaluated with the SAME eval_harness used for the baselines, including the
cold-start warm/cold split - so the comparison to Phase 1 is apples-to-apples.

Run:
    python train_gnn.py /path/to/graph train
    python train_gnn.py /path/to/graph train_test
    python train_gnn.py /path/to/graph train_test /path/to/baseline_results.csv

The optional 3rd argument points at the baseline_results.csv written by
train_baselines.py FOR THE SAME DATASET, so the closing comparison is computed
live from that run instead of a fixed number. (Previous versions of this script
hardcoded the original ASOS baseline's numbers - ~0.833 overall AUC, ~0.65
cold-customer AUC - into the print statements. Those were only ever true for
that one dataset and silently became wrong/misleading the moment this script
ran against different data, e.g. the India synthetic set. Fixed here: nothing
is printed as a comparison unless it was actually measured on this run.)
"""

import os
import sys

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, to_hetero

from eval_harness import full_report

CONFIG = {
    "graph_dir": "./graph",
    "hidden_dim": 64,
    "epochs": 50,
    "lr": 0.005,
    "weight_decay": 5e-4,
    "seed": 42,
    "baseline_csv": None,  # optional: path to THIS dataset's baseline_results.csv
}


def log(msg=""):
    print(msg)


class GNNEncoder(torch.nn.Module):
    """Two-layer GraphSAGE encoder. to_hetero() will duplicate this per edge
    type so both customer and product nodes get updated representations."""
    def __init__(self, hidden):
        super().__init__()
        self.conv1 = SAGEConv((-1, -1), hidden)
        self.conv2 = SAGEConv((-1, -1), hidden)

    def forward(self, x, edge_index):
        x = F.relu(self.conv1(x, edge_index))
        x = self.conv2(x, edge_index)
        return x


class EdgeDecoder(torch.nn.Module):
    """Given customer+product embeddings for each edge (plus optional per-order
    edge features like COD/tier/courier), predict a return logit. The edge
    features are known at order time and present even for cold customers, so
    feeding them here is what lets the GNN match the tabular baselines' access
    to COD rather than being blind to it."""
    def __init__(self, hidden, edge_dim=0):
        super().__init__()
        self.edge_dim = edge_dim
        self.lin1 = torch.nn.Linear(2 * hidden + edge_dim, hidden)
        self.lin2 = torch.nn.Linear(hidden, 1)

    def forward(self, z_cust, z_prod, edge_index, edge_attr=None):
        row, col = edge_index
        parts = [z_cust[row], z_prod[col]]
        if self.edge_dim and edge_attr is not None:
            parts.append(edge_attr)
        h = torch.cat(parts, dim=-1)
        h = F.relu(self.lin1(h))
        return self.lin2(h).squeeze(-1)


class Model(torch.nn.Module):
    def __init__(self, metadata, hidden, edge_dim=0):
        super().__init__()
        self.encoder = to_hetero(GNNEncoder(hidden), metadata, aggr="sum")
        self.decoder = EdgeDecoder(hidden, edge_dim=edge_dim)

    def forward(self, x_dict, edge_index_dict, edge_label_index, edge_attr=None):
        z = self.encoder(x_dict, edge_index_dict)
        return self.decoder(z["customer"], z["product"], edge_label_index, edge_attr)


def load_baseline_comparison(csv_path):
    """Read a baseline_results.csv (written by train_baselines.py) and return
    (best_model_name, per-slice-not-available, overall_auc) - or None if the
    file can't be read / doesn't have the expected shape. Never raises: a
    missing or malformed baseline file should degrade to 'no comparison',
    never crash the GNN run."""
    if not csv_path:
        return None
    if not os.path.exists(csv_path):
        log(f"\n(baseline_csv given but not found at {csv_path} - skipping comparison)")
        return None
    try:
        base = pd.read_csv(csv_path, index_col=0)
        if "auc" not in base.columns:
            log(f"\n(baseline_csv at {csv_path} has no 'auc' column - skipping "
                f"comparison; columns found: {list(base.columns)})")
            return None
        best_model = base["auc"].idxmax()
        best_auc = float(base["auc"].max())
        return best_model, best_auc
    except Exception as e:
        log(f"\n(couldn't read baseline_csv at {csv_path}: {type(e).__name__}: {e} "
            f"- skipping comparison)")
        return None


def main():
    if len(sys.argv) > 1:
        CONFIG["graph_dir"] = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "train"
    if len(sys.argv) > 3:
        CONFIG["baseline_csv"] = sys.argv[3]

    torch.manual_seed(CONFIG["seed"])
    np.random.seed(CONFIG["seed"])

    log("=" * 70)
    log(f"PHASE 2c - GraphSAGE  (mode={mode})")
    log("=" * 70)

    path = os.path.join(CONFIG["graph_dir"], f"graph_{mode}.pt")
    data = torch.load(path, weights_only=False)
    edge = data["customer", "buys", "product"]
    log(data)

    train_mask = edge.train_mask
    test_mask = edge.test_mask
    y = edge.edge_label

    # per-order edge features (COD/tier/courier/channel), if build_graph attached
    # them. Split the same way as edges so train/eval each get their own slice.
    has_edge_attr = "edge_attr" in edge
    if has_edge_attr:
        edge_attr_all = edge.edge_attr
        edge_dim = edge_attr_all.size(1)
        names = getattr(edge, "edge_attr_names", None)
        log(f"using {edge_dim} per-order edge features"
            + (f": {list(names)}" if names is not None else ""))
        edge_attr_train = edge_attr_all[train_mask]
        edge_attr_test = edge_attr_all[test_mask]
    else:
        edge_dim = 0
        edge_attr_train = edge_attr_test = None
        log("no edge_attr on graph - GNN runs node-only (rebuild graph with "
            "ord__ features for a fair vs-baseline comparison)")

    # message-passing graph = TRAIN edges only (never let the model see test
    # edges as graph structure - that would leak). Both directions, so both
    # customer and product nodes get updated.
    mp_edge_index = edge.edge_index[:, train_mask]
    x_dict = {"customer": data["customer"].x, "product": data["product"].x}
    edge_index_dict = {
        ("customer", "buys", "product"): mp_edge_index,
        ("product", "rev_buys", "customer"): mp_edge_index.flip(0),
    }

    model = Model(data.metadata(), CONFIG["hidden_dim"], edge_dim=edge_dim)
    opt = torch.optim.Adam(model.parameters(), lr=CONFIG["lr"],
                           weight_decay=CONFIG["weight_decay"])

    train_ei = edge.edge_index[:, train_mask]
    test_ei = edge.edge_index[:, test_mask]
    y_train = y[train_mask]
    y_test = y[test_mask]

    # class weight for the (mild) imbalance, matching the baseline's spirit
    pos_weight = ((y_train == 0).sum() / (y_train == 1).sum().clamp(min=1)).clamp(0.2, 5.0)

    log(f"\ntraining {CONFIG['epochs']} epochs "
        f"({train_mask.sum().item():,} train edges, {test_mask.sum().item():,} test edges)")
    model.train()
    for ep in range(1, CONFIG["epochs"] + 1):
        opt.zero_grad()
        out = model(x_dict, edge_index_dict, train_ei, edge_attr_train)
        loss = F.binary_cross_entropy_with_logits(out, y_train, pos_weight=pos_weight)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        opt.step()
        if ep % 5 == 0 or ep == 1:
            log(f"  epoch {ep:3d}  loss {loss.item():.4f}")

    # --- evaluate on test edges ---
    model.eval()
    with torch.no_grad():
        test_logits = model(x_dict, edge_index_dict, test_ei, edge_attr_test)
        test_prob = torch.sigmoid(test_logits).numpy()

    y_test_np = y_test.numpy()
    cust_no_hist = edge.customer_no_history[test_mask].numpy() if "customer_no_history" in edge else None
    prod_no_hist = edge.product_no_history[test_mask].numpy() if "product_no_history" in edge else None
    cust_rr = edge.cust_return_rate[test_mask].numpy() if "cust_return_rate" in edge else None

    overall = full_report(f"GraphSAGE ({mode})", y_test_np, test_prob,
                          customer_return_rate=cust_rr,
                          customer_no_history=cust_no_hist,
                          product_no_history=prod_no_hist)

    # --- comparison vs THIS run's own baselines (no hardcoded numbers) ---
    cmp = load_baseline_comparison(CONFIG["baseline_csv"])
    gnn_auc = overall.get("auc")
    if cmp is not None and gnn_auc is not None:
        best_model, best_auc = cmp
        delta = gnn_auc - best_auc
        log(f"\nBest Phase 1 tabular baseline on THIS dataset: "
            f"{best_model} overall auc={best_auc:.4f}")
        log(f"GraphSAGE overall auc={gnn_auc:.4f}  ({delta:+.4f} vs best baseline)")
        if delta <= 0:
            log("GraphSAGE did not beat the tabular baseline's OVERALL auc on this run.")
    else:
        log("\n(No baseline_csv given, or it couldn't be read - pass the path to "
            "THIS dataset's baseline_results.csv as a 3rd argument for a live "
            "comparison instead of eyeballing two separate printouts, e.g.:\n"
            "  python train_gnn.py data/graph_india train_test "
            "data/features_india/baseline_results.csv)")

    if mode == "train_test":
        log("\nThe customer cold-start = cold row above is the key number: compare "
            "it directly against the SAME row in your train_baselines.py output "
            "for this dataset (not any other run's numbers) to see whether graph "
            "structure helped on genuinely unseen customers.")


if __name__ == "__main__":
    main()