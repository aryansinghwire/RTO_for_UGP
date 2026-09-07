#!/usr/bin/env python3
"""
Phase 3, Milestone 1 - Graph Transformer encoder.

The core of the Returnformer. Identical to the Phase 2 GraphSAGE setup in every
way EXCEPT the message-passing layer: SAGEConv -> TransformerConv. Where
GraphSAGE averages a node's neighbours equally, the Graph Transformer uses
learned ATTENTION to weight neighbours by relevance - the paper's central
encoder idea, and the reason it's expected to beat plain GNNs.

Same graph object, same eval_harness, same train / train_test modes, same
edge-level decoder as Phase 2, so results are directly comparable to the
GraphSAGE numbers (Option 1: 0.855 AUC, Option 2: 0.876 / 0.767 cold).

Paper config (Table 3): 2 layers, 4 attention heads, softmax input clamped to
[-5, +5] for numerical stability.

Run:
    python train_transformer.py /path/to/graph train
    python train_transformer.py /path/to/graph train_test
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
    "hidden_dim": 64,
    "heads": 4,          # paper: 4 attention heads
    "layers": 2,         # paper: 2 Graph Transformer layers
    "epochs": 50,
    "lr": 0.005,
    "weight_decay": 5e-4,
    "clamp": 5.0,        # paper: clamp softmax input to [-5, +5]
    "seed": 42,
}


def log(msg=""):
    print(msg)


class TransformerEncoder(torch.nn.Module):
    """Two TransformerConv layers. Each layer uses multi-head attention over a
    node's neighbours. We divide hidden_dim by heads so concatenated multi-head
    output returns to hidden_dim (standard multi-head sizing)."""
    def __init__(self, hidden, heads, layers, clamp):
        super().__init__()
        assert hidden % heads == 0, "hidden_dim must be divisible by heads"
        per_head = hidden // heads
        self.clamp = clamp
        self.convs = torch.nn.ModuleList()
        for _ in range(layers):
            # (-1, -1) lets PyG infer the (bipartite) input dims lazily;
            # concat=True gives heads*per_head = hidden output per layer.
            self.convs.append(
                TransformerConv((-1, -1), per_head, heads=heads, concat=True)
            )

    def forward(self, x, edge_index):
        for i, conv in enumerate(self.convs):
            x = conv(x, edge_index)
            if i < len(self.convs) - 1:
                x = F.relu(x)
            # clamp keeps activations bounded (numerical stability, per paper)
            x = torch.clamp(x, -self.clamp, self.clamp)
        return x


class EdgeDecoder(torch.nn.Module):
    """Given customer+product embeddings for each edge, predict a return logit.
    Same decoder as the Phase 2 GraphSAGE model, so the encoder is the only
    thing that changed."""
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
    def __init__(self, metadata, cfg):
        super().__init__()
        enc = TransformerEncoder(cfg["hidden_dim"], cfg["heads"],
                                 cfg["layers"], cfg["clamp"])
        self.encoder = to_hetero(enc, metadata, aggr="sum")
        self.decoder = EdgeDecoder(cfg["hidden_dim"])

    def forward(self, x_dict, edge_index_dict, edge_label_index):
        z = self.encoder(x_dict, edge_index_dict)
        return self.decoder(z["customer"], z["product"], edge_label_index)


def main():
    if len(sys.argv) > 1:
        CONFIG["graph_dir"] = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "train"
    suffix = sys.argv[3] if len(sys.argv) > 3 else ""   # e.g. "_n2v"

    torch.manual_seed(CONFIG["seed"])
    np.random.seed(CONFIG["seed"])

    log("=" * 70)
    log(f"PHASE 3.1 - GRAPH TRANSFORMER  (mode={mode}{', graph=' + mode + suffix if suffix else ''})")
    log(f"  {CONFIG['layers']} layers, {CONFIG['heads']} heads, "
        f"hidden={CONFIG['hidden_dim']}, clamp=+/-{CONFIG['clamp']}")
    log("=" * 70)

    path = os.path.join(CONFIG["graph_dir"], f"graph_{mode}{suffix}.pt")
    data = torch.load(path, weights_only=False)
    edge = data["customer", "buys", "product"]
    log(data)

    train_mask = edge.train_mask
    test_mask = edge.test_mask
    y = edge.edge_label

    # message-passing graph = TRAIN edges only (both directions), never test.
    mp_edge_index = edge.edge_index[:, train_mask]
    x_dict = {"customer": data["customer"].x, "product": data["product"].x}
    edge_index_dict = {
        ("customer", "buys", "product"): mp_edge_index,
        ("product", "rev_buys", "customer"): mp_edge_index.flip(0),
    }

    train_ei = edge.edge_index[:, train_mask]
    test_ei = edge.edge_index[:, test_mask]
    y_train = y[train_mask]
    y_test = y[test_mask]

    pos_weight = ((y_train == 0).sum() / (y_train == 1).sum().clamp(min=1)).clamp(0.2, 5.0)

    model = Model(data.metadata(), CONFIG)
    opt = torch.optim.Adam(model.parameters(), lr=CONFIG["lr"],
                           weight_decay=CONFIG["weight_decay"])

    log(f"\ntraining {CONFIG['epochs']} epochs "
        f"({train_mask.sum().item():,} train edges, {test_mask.sum().item():,} test edges)")
    model.train()
    for ep in range(1, CONFIG["epochs"] + 1):
        opt.zero_grad()
        out = model(x_dict, edge_index_dict, train_ei)
        loss = F.binary_cross_entropy_with_logits(out, y_train, pos_weight=pos_weight)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        opt.step()
        if ep % 5 == 0 or ep == 1:
            log(f"  epoch {ep:3d}  loss {loss.item():.4f}")

    model.eval()
    with torch.no_grad():
        test_logits = model(x_dict, edge_index_dict, test_ei)
        test_prob = torch.sigmoid(test_logits).numpy()

    y_test_np = y_test.numpy()
    cust_no_hist = edge.customer_no_history[test_mask].numpy() if "customer_no_history" in edge else None
    prod_no_hist = edge.product_no_history[test_mask].numpy() if "product_no_history" in edge else None
    cust_rr = edge.cust_return_rate[test_mask].numpy() if "cust_return_rate" in edge else None

    full_report(f"Graph Transformer ({mode})", y_test_np, test_prob,
                customer_return_rate=cust_rr,
                customer_no_history=cust_no_hist,
                product_no_history=prod_no_hist)

    log("\nCompare to: baseline ~0.833 | GraphSAGE 0.855 (train) / 0.876 (train_test)")
    if mode == "train_test":
        log("Key number: customer cold-start = cold. GraphSAGE got 0.767 there -")
        log("does attention widen the cold-customer lift?")


if __name__ == "__main__":
    main()