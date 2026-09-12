# Archive

Work that is **not part of the current running system** (the GraphSAGE scoring
pipeline + ops-dashboard prototype), kept here rather than deleted so it stays
recoverable and so the project history stays honest.

Nothing in the live system imports or reads anything in this directory.

## What's here

### `ablations/` — Phase 3 architecture experiments
The Returnformer components that were built, evaluated, and found **not** to
improve on plain GraphSAGE on this data (see `checkpoint_phase0_phase3.md` §5):

| File | Phase | Result |
|---|---|---|
| `train_transformer.py` | 3.1 | Graph Transformer — tie with GraphSAGE (0.874 vs 0.876 AUC) |
| `add_node2vec.py` | 3.2 | Node2Vec embeddings — hurt cold-start (0.767 → 0.701) |
| `train_fusion.py` | 3.3 | Attention fusion — partial recovery, still net negative (0.689) |

These are the evidence for the project's headline finding, so they're preserved
deliberately. They're archived only because the shipped system uses GraphSAGE.

### `india/` — India RTO/COD adaptation
The next PRD phase, parked because the experiment results were unreliable:
- `india_synth_generator.py` — synthetic India RTO data generator
- `tune_threshold.py` — decision-threshold tuning written around India economics
  (~30% RTO base rate, per-order cost in rupees)
- `checkpoint_india_phase0_complete.md` — India Phase 0 write-up
- `results_poscontrol.txt` — positive-control run (part of the India work)

### `checkpoints/` — superseded progress docs
`checkpoint_phase0_phase1.md` and `checkpoint_phase0_phase2.md`. Both are fully
subsumed by `checkpoint_phase0_phase3.md`, which stays at the repo root.

### `diagnostics/` — one-off scripts
`checks.py` — the Phase 0 scratch script that root-caused the orphan-edge
finding (node tables only contain entities with ≥1 historical return). Has
hardcoded absolute paths; kept for the record, not for reuse.

### `data/` — archived datasets (~1.1 GB, gitignored)
Not in git — the repo's existing `data/` ignore rule covers this path too.

| Path | What |
|---|---|
| `features_india*`, `graph_india*`, `synth_india*` | India synthetic datasets (10K and 500K scales) |
| `features_poscontrol`, `graph_poscontrol`, `synth_poscontrol` | Positive-control datasets (India work) |
| `graph_superseded/` | Train-only-mode graphs and the Node2Vec-augmented graphs (`*_n2v.pt`) |
| `graph_duplicate_toplevel/` | Old top-level `graph/` dir — byte-identical duplicates (md5-verified) of files already in `data/graph/` |
| `catboost_info/` | CatBoost's auto-generated training logs (regenerated on any CatBoost run) |

## Restoring something

Everything moved with `git mv`, so history follows the rename:

```bash
git mv archive/ablations/train_transformer.py .   # code/docs
mv archive/data/synth_india data/                 # datasets
```
