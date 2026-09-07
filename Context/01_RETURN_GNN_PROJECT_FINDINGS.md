# Return GNN Project — Experimental Findings

## Objective
Predict whether an order/item will be returned before payment.

The project reproduced and evaluated Returnformer-style graph modelling on the ASOS fashion-returns dataset, then tested whether each added architectural component improved performance.

## Data facts
- ~1.34M training / ~1.43M test events in the project summary.
- ~1.4M customers.
- ~410K product variants.
- Graph: customer/product bipartite graph; orders are labelled edges.
- Graph sparsity: ~1.1 edges per node.
- ~78% of test customers are unseen during training.
- Cold-start therefore dominates realistic deployment and is reported separately.

## Pipeline
1. Data profiling and cleaning.
2. Tabular baselines: XGBoost, LightGBM, CatBoost, MLP.
3. Bipartite graph + GraphSAGE.
4. Graph Transformer.
5. Graph Transformer + Node2Vec.
6. Graph Transformer + Node2Vec + attention fusion.

## Results

| Model | Overall AUC | Cold-customer AUC | Verdict |
|---|---:|---:|---|
| Best tabular baseline | 0.833 | ~0.65 | Reference floor |
| **GraphSAGE** | **0.876** | **0.767** | **Best model built** |
| Graph Transformer | 0.874 | 0.761 | No gain over GraphSAGE |
| GT + Node2Vec (concat) | 0.859 | 0.701 | Degraded |
| GT + Node2Vec + Fusion | 0.864 | 0.689 | Degraded |

F1 at an untuned 0.5 threshold clustered around 0.73–0.78.

## Main conclusion
The useful graph gain comes from moving from flat tabular features to direct graph message passing. GraphSAGE captures this gain without the additional global-topology machinery.

The project found:
- Attention did not improve GraphSAGE-level performance.
- Node2Vec degraded performance.
- Node2Vec especially hurt cold-start.
- Attention fusion did not recover the degradation.
- GraphSAGE is cheaper because it does not require a separate embedding-training step.

## Interpretation
The graph is sparse and many customers appear only once. In this environment, a node's global graph position is less useful than information obtained from direct neighbours and node features. Global topological embeddings can therefore become redundant/noisy.

This is a dataset-specific finding, not a universal rejection of Node2Vec/GEA/Transformers.

## Why paper and project differ
The Returnformer paper operates on a large graph where partitioning can fragment useful global structure. Its Node2Vec + GEA components explicitly address this.

The project uses a deliberately small/sparse subgraph. It avoids the same partitioning problem, so the motivation for global topological recovery is weaker.

A useful future test is a denser-subgraph experiment to see whether the value of global topology increases with graph density.

## GEA and KAN
GEA was not implemented because the project works at single-subgraph scale; GEA's role is to reconnect information across partitioned subgraphs. Testing it would require full-graph processing considered infeasible on available hardware.

KAN was not implemented because:
- the paper reports only ~0.5 F1 benefit;
- all additional architectural components tested in this project were neutral-to-negative;
- the expected payoff did not justify the complexity.

## Metric choice
AUC is primary because it is threshold-independent and the product threshold is a business decision.

Use:
- AUC for model selection.
- PR-AUC as an additional ranking metric.
- Precision/recall/F1 at the actual operating threshold.

F1@0.5 should not be treated as the definitive model ranking.

## Evidence boundary
The project supports GraphSAGE as the best validated model for this return dataset. It does not prove GraphSAGE is best for the India RTO problem; RTO requires its own labelled data and ablation study.
