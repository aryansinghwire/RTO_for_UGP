#!/usr/bin/env python3
"""
Phase 3, Milestone 3 - Attention Fusion of original + structural features.

Milestone 2 concatenated the Node2Vec structural embeddings onto the original
features and let the model sort it out - it couldn't, and the near-irrelevant
structural columns diluted the genuinely-predictive original features (cold-
customer AUC fell from ~0.76 to ~0.71).

Attention fusion (paper Equations 1-4) does the smart thing instead: it learns,
per node, HOW MUCH to weight the original features vs. the structural embeddings,
and blends them by that learned weight. The mechanism:

    X_o_hat = X_o W_o                         (project original features)
    X_s_hat = X_s W_s                         (project structural features)
    a_o = tanh(X_o_hat . q_o)                 (score each source)
    a_s = tanh(X_s_hat . q_s)
    [w_o, w_s] = softmax([a_o, a_s])          (weights sum to 1)
    h = w_o * X_o_hat + w_s * X_s_hat         (weighted blend)

Why this is the right test now: we already established the structural embeddings
are real but unhelpful on this sparse graph. A correctly-working fusion should
LEARN to down-weight them (w_s -> ~0), recovering the clean features-only
performance instead of the diluted concatenation. So this milestone tests
whether the fusion mechanism protects the model from an unhelpful feature source,
exactly as designed. The script prints the learned average weights so you can
SEE what it decided.

Run:
    python train_fusion.py /path/to/graph train
    python train_fusion.py /path/to/graph train_test
"""

import os
import sys

import numpy as np
import torch
import torch.nn.functional as F
from torch_geometric.nn import TransformerConv, to_hetero

from eval_harness import full_report

CONFIG = {
    "graph_dir": "./graph",
    "fusion_dim": 64,     # common dim both sources are projected to
    "hidden_dim": 64,
    "heads": 4,
    "layers": 2,
    "epochs": 50,
    "lr": 0.005,
    "weight_decay": 5e-4,
    "clamp": 5.0,
    "seed": 42,
}


def log(msg=""):
    print(msg)


class AttentionFusion(torch.nn.Module):
    """Paper Equations 1-4. Projects original + structural features to a common
    dim, scores each with a learned attention vector, softmax-normalizes the two
    scores into weights, and returns the weighted blend. Exposes the mean weights
    so we can inspect what it learned."""
    def __init__(self, dim_orig, dim_struct, fusion_dim):
        super().__init__()
        self.W_o = torch.nn.Linear(dim_orig, fusion_dim, bias=False)
        self.W_s = torch.nn.Linear(dim_struct, fusion_dim, bias=False)
        self.q_o = torch.nn.Parameter(torch.randn(fusion_dim))
        self.q_s = torch.nn.Parameter(torch.randn(fusion_dim))
        self.last_w = None   # (w_o_mean, w_s_mean) for inspection

    def forward(self, x_orig, x_struct):
        h_o = self.W_o(x_orig)                       # [N, fusion_dim]
        h_s = self.W_s(x_struct)                     # [N, fusion_dim]
        a_o = torch.tanh(h_o @ self.q_o)             # [N]
        a_s = torch.tanh(h_s @ self.q_s)             # [N]
        w = torch.softmax(torch.stack([a_o, a_s], dim=1), dim=1)  # [N, 2]
        self.last_w = (w[:, 0].mean().item(), w[:, 1].mean().item())
        return w[:, 0:1] * h_o + w[:, 1:2] * h_s     # [N, fusion_dim]


class TransformerEncoder(torch.nn.Module):
    def __init__(self, hidden, heads, layers, clamp):
        super().__init__()
        assert hidden % heads == 0
        per_head = hidden // heads
        self.clamp = clamp
        self.convs = torch.nn.ModuleList(
            [TransformerConv((-1, -1), per_head, heads=heads, concat=True)
             for _ in range(layers)]
        )

    def forward(self, x, edge_index):
        for i, conv in enumerate(self.convs):
            x = conv(x, edge_index)
            if i < len(self.convs) - 1:
                x = F.relu(x)
            x = torch.clamp(x, -self.clamp, self.clamp)
        return x


class EdgeDecoder(torch.nn.Module):
    def __init__(self, hidden):
        super().__init__()
        self.lin1 = torch.nn.Linear(2 * hidden, hidden)
        self.lin2 = torch.nn.Linear(hidden, 1)

    def forward(self, z_cust, z_prod, edge_index):
        row, col = edge_index
        h = torch.cat([z_cust[row], z_prod[col]], dim=-1)
        h = F.relu(self.lin1(h))
        return self.lin2(h).squeeze(-1)


class Model(torch.nn.Module):
    """Fusion (per node type) -> Graph Transformer encoder -> edge decoder."""
    def __init__(self, metadata, dims, cfg):
        super().__init__()
        fd = cfg["fusion_dim"]
        self.fuse_cust = AttentionFusion(dims["cust_orig"], dims["cust_struct"], fd)
        self.fuse_prod = AttentionFusion(dims["prod_orig"], dims["prod_struct"], fd)
        enc = TransformerEncoder(cfg["hidden_dim"], cfg["heads"], cfg["layers"], cfg["clamp"])
        self.encoder = to_hetero(enc, metadata, aggr="sum")
        self.decoder = EdgeDecoder(cfg["hidden_dim"])

    def forward(self, feats, edge_index_dict, edge_label_index):
        x_dict = {
            "customer": self.fuse_cust(feats["cust_orig"], feats["cust_struct"]),
            "product": self.fuse_prod(feats["prod_orig"], feats["prod_struct"]),
        }
        z = self.encoder(x_dict, edge_index_dict)
        return self.decoder(z["customer"], z["product"], edge_label_index)


def split_orig_struct(node_store):
    """Recover the original vs structural feature blocks. x = [orig || struct],
    and x_struct is stored separately, so orig = x[:, :-struct_dim]."""
    x = node_store.x
    x_struct = node_store.x_struct
    d_struct = x_struct.shape[1]
    x_orig = x[:, :x.shape[1] - d_struct]
    return x_orig, x_struct


def main():
    if len(sys.argv) > 1:
        CONFIG["graph_dir"] = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "train"

    torch.manual_seed(CONFIG["seed"])
    np.random.seed(CONFIG["seed"])

    log("=" * 70)
    log(f"PHASE 3.3 - ATTENTION FUSION + GRAPH TRANSFORMER  (mode={mode})")
    log("=" * 70)

    path = os.path.join(CONFIG["graph_dir"], f"graph_{mode}_n2v.pt")
    data = torch.load(path, weights_only=False)
    edge = data["customer", "buys", "product"]

    cust_orig, cust_struct = split_orig_struct(data["customer"])
    prod_orig, prod_struct = split_orig_struct(data["product"])
    log(f"customer: {cust_orig.shape[1]} original + {cust_struct.shape[1]} structural feats")
    log(f"product : {prod_orig.shape[1]} original + {prod_struct.shape[1]} structural feats")

    dims = {
        "cust_orig": cust_orig.shape[1], "cust_struct": cust_struct.shape[1],
        "prod_orig": prod_orig.shape[1], "prod_struct": prod_struct.shape[1],
    }

    train_mask = edge.train_mask
    test_mask = edge.test_mask
    y = edge.edge_label

    mp_edge_index = edge.edge_index[:, train_mask]
    edge_index_dict = {
        ("customer", "buys", "product"): mp_edge_index,
        ("product", "rev_buys", "customer"): mp_edge_index.flip(0),
    }
    feats = {"cust_orig": cust_orig, "cust_struct": cust_struct,
             "prod_orig": prod_orig, "prod_struct": prod_struct}

    train_ei = edge.edge_index[:, train_mask]
    test_ei = edge.edge_index[:, test_mask]
    y_train, y_test = y[train_mask], y[test_mask]
    pos_weight = ((y_train == 0).sum() / (y_train == 1).sum().clamp(min=1)).clamp(0.2, 5.0)

    model = Model(data.metadata(), dims, CONFIG)
    opt = torch.optim.Adam(model.parameters(), lr=CONFIG["lr"],
                           weight_decay=CONFIG["weight_decay"])

    log(f"\ntraining {CONFIG['epochs']} epochs "
        f"({train_mask.sum().item():,} train edges, {test_mask.sum().item():,} test edges)")
    model.train()
    for ep in range(1, CONFIG["epochs"] + 1):
        opt.zero_grad()
        out = model(feats, edge_index_dict, train_ei)
        loss = F.binary_cross_entropy_with_logits(out, y_train, pos_weight=pos_weight)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        opt.step()
        if ep % 10 == 0 or ep == 1:
            wc = model.fuse_cust.last_w
            wp = model.fuse_prod.last_w
            log(f"  epoch {ep:3d}  loss {loss.item():.4f}  "
                f"cust[orig={wc[0]:.2f} struct={wc[1]:.2f}] "
                f"prod[orig={wp[0]:.2f} struct={wp[1]:.2f}]")

    model.eval()
    with torch.no_grad():
        test_logits = model(feats, edge_index_dict, test_ei)
        test_prob = torch.sigmoid(test_logits).numpy()

    y_test_np = y_test.numpy()
    cust_no_hist = edge.customer_no_history[test_mask].numpy() if "customer_no_history" in edge else None
    prod_no_hist = edge.product_no_history[test_mask].numpy() if "product_no_history" in edge else None
    cust_rr = edge.cust_return_rate[test_mask].numpy() if "cust_return_rate" in edge else None

    full_report(f"Attention Fusion + GT ({mode})", y_test_np, test_prob,
                customer_return_rate=cust_rr,
                customer_no_history=cust_no_hist,
                product_no_history=prod_no_hist)

    wc, wp = model.fuse_cust.last_w, model.fuse_prod.last_w
    log(f"\nLearned fusion weights (final):")
    log(f"  customer: original={wc[0]:.3f}, structural={wc[1]:.3f}")
    log(f"  product : original={wp[0]:.3f}, structural={wp[1]:.3f}")
    log("Interpretation: if structural weight is LOW, fusion learned the Node2Vec")
    log("embeddings don't help and down-weighted them (recovering clean-feature")
    log("performance). If HIGH, it found them useful. Either way it's informative.")
    log("\nCompare cold-customer AUC to: features-only 0.761 | concat 0.648")


if __name__ == "__main__":
    main()
