#!/usr/bin/env python3
"""
Phase 3, Milestone 2 - Node2Vec structural embeddings.

Adds each node's STRUCTURAL POSITION in the graph to its features. Milestone 1
showed that swapping in attention alone didn't help - because a cold customer
with one edge has no personal neighbourhood for any encoder to aggregate. Node2Vec
fixes exactly that: it learns a vector describing where each node sits in the
GLOBAL graph topology, independent of that node's own edge count.

LEAKAGE-SAFE DESIGN: Node2Vec walks are computed on the TRAINING edges only.
Using test-period edges to build embeddings would leak future connectivity into
training. Cold test customers still get a real structural embedding, derived
purely from how the training graph is shaped around the products they touch.

This milestone does the SIMPLE correct version: compute the embeddings and
CONCATENATE them onto existing node features. The learned attention-fusion is
milestone 3, kept separate so any change is attributable to the right piece.

Node2Vec params: the paper uses p=q=0.8, but pyg-lib only supports uniform
walks (p=q=1) - effectively DeepWalk. Since 0.8 is already near-uniform, the
difference in the resulting embeddings is expected to be negligible.
Requires pyg-lib.

Run:
    python add_node2vec.py /path/to/graph train
    python add_node2vec.py /path/to/graph train_test
"""

import os
import sys

import torch
from torch_geometric.nn import Node2Vec

CONFIG = {
    "graph_dir": "./graph",
    "embed_dim": 32,
    "walk_length": 40,   # longer than default (20) to traverse sparse graph, but not 80 (too slow on CPU)
    "context_size": 10,  # back to default - wider window multiplies cost for little gain
    "walks_per_node": 10,  # back to default - this was an 2x cost multiplier
    "p": 1.0,  # pyg-lib only supports uniform walks; 0.8 was near-uniform anyway
    "q": 1.0,  # see note on p
    "epochs": 20,   # fewer epochs - loss plateaus early anyway
    "lr": 0.01,
    "batch_size": 128,
    "seed": 42,
}


def log(msg=""):
    print(msg)


def build_homogeneous_train_edges(data):
    """Flatten the bipartite graph into one homogeneous node space (customers
    first, products offset by n_customers), using TRAIN edges only, undirected."""
    edge = data["customer", "buys", "product"]
    n_cust = data["customer"].num_nodes
    n_prod = data["product"].num_nodes

    train_mask = edge.train_mask
    ei = edge.edge_index[:, train_mask]
    cust_idx = ei[0]
    prod_idx = ei[1] + n_cust

    src = torch.cat([cust_idx, prod_idx])
    dst = torch.cat([prod_idx, cust_idx])
    edge_index = torch.stack([src, dst], dim=0)
    return edge_index, n_cust + n_prod, n_cust, n_prod


def main():
    if len(sys.argv) > 1:
        CONFIG["graph_dir"] = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "train"

    torch.manual_seed(CONFIG["seed"])
    device = "cpu"

    log("=" * 70)
    log(f"PHASE 3.2 - NODE2VEC STRUCTURAL EMBEDDINGS  (mode={mode})")
    log(f"  dim={CONFIG['embed_dim']}, p={CONFIG['p']}, q={CONFIG['q']}, "
        f"walks on TRAIN edges only (leakage-safe)")
    log("=" * 70)

    path = os.path.join(CONFIG["graph_dir"], f"graph_{mode}.pt")
    data = torch.load(path, weights_only=False)

    edge_index, total_nodes, n_cust, n_prod = build_homogeneous_train_edges(data)
    log(f"homogeneous graph for Node2Vec: {total_nodes:,} nodes "
        f"({n_cust:,} customers + {n_prod:,} products), "
        f"{edge_index.shape[1]:,} directed edges (train only)")

    n2v = Node2Vec(
        edge_index,
        embedding_dim=CONFIG["embed_dim"],
        walk_length=CONFIG["walk_length"],
        context_size=CONFIG["context_size"],
        walks_per_node=CONFIG["walks_per_node"],
        num_negative_samples=5,   # was default 1 - more negatives -> sharper,
                                  # more discriminative embeddings
        p=CONFIG["p"],
        q=CONFIG["q"],
        num_nodes=total_nodes,
        sparse=True,
    ).to(device)

    loader = n2v.loader(batch_size=CONFIG["batch_size"], shuffle=True, num_workers=0)
    opt = torch.optim.SparseAdam(list(n2v.parameters()), lr=CONFIG["lr"])

    log(f"\ntraining Node2Vec {CONFIG['epochs']} epochs...")
    n2v.train()
    first_loss, last_loss = None, None
    for ep in range(1, CONFIG["epochs"] + 1):
        total = 0.0
        for pos_rw, neg_rw in loader:
            opt.zero_grad()
            loss = n2v.loss(pos_rw.to(device), neg_rw.to(device))
            loss.backward()
            opt.step()
            total += loss.item()
        avg = total / len(loader)
        if ep == 1:
            first_loss = avg
        last_loss = avg
        if ep % 5 == 0 or ep == 1:
            log(f"  epoch {ep:3d}  loss {avg:.4f}")

    drop = (first_loss - last_loss) / first_loss * 100 if first_loss else 0
    log(f"  loss moved {first_loss:.4f} -> {last_loss:.4f} ({drop:.0f}% drop)")
    if drop < 15:
        log("  WARNING: loss barely moved - graph likely too sparse for Node2Vec")
        log("  to learn meaningful structure. Embeddings may be near-noise.")

    n2v.eval()
    with torch.no_grad():
        emb = n2v.embedding.weight.detach().cpu()
    cust_emb = emb[:n_cust]
    prod_emb = emb[n_cust:]

    data["customer"].x = torch.cat([data["customer"].x, cust_emb], dim=1)
    data["product"].x = torch.cat([data["product"].x, prod_emb], dim=1)
    data["customer"].x_struct = cust_emb
    data["product"].x_struct = prod_emb

    log(f"\nnode features after concat: "
        f"customer x={tuple(data['customer'].x.shape)}, "
        f"product x={tuple(data['product'].x.shape)}")

    out = os.path.join(CONFIG["graph_dir"], f"graph_{mode}_n2v.pt")
    torch.save(data, out)
    log(f"saved augmented graph to {out}")
    log("Next: train_transformer.py on the _n2v graph:")
    log(f"  python train_transformer.py {CONFIG['graph_dir']} {mode} _n2v")


if __name__ == "__main__":
    main()