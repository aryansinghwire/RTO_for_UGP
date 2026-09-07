# E-commerce Risk Prediction — Master Context

## Purpose
This file is the compact, retrieval-oriented project context. It combines the three supplied documents:
1. `returns_gnn_summary.pdf` — project-specific return-prediction experiments.
2. `entropy-28-00072-v2.pdf` — the Returnformer research paper.
3. `RTO_Risk_Engine_PRD_Realtime_v2.pdf` — product requirements for an India D2C RTO risk engine.

Use this file for high-level questions. Use the individual files when exact technical details, equations, paper wording, or PRD requirements are needed.

---

## 1. Core Problem

### Return prediction research
Goal: predict whether an e-commerce order/item will be returned before payment, so return risk can be identified early.

The project reproduced and evaluated the Returnformer approach on the ASOS fashion-returns dataset and compared increasingly complex graph architectures against tabular baselines.

### India RTO product
The commercial product is scoped differently: MVP predicts **pre-delivery RTO for COD orders**, meaning non-acceptance/non-delivery such as COD refusal, customer unreachable, or failed delivery attempt. Post-delivery return prediction is explicitly out of MVP scope.

This distinction matters: **return and RTO are different prediction targets and should not be treated as the same label.**

---

## 2. Research Paper: Returnformer

Paper: Cao, Zhang & Li, “Returnformer: A Graph Transformer-Based Model for Predicting Product Returns in E-Commerce,” *Entropy* 2026, 28, 72.

Dataset:
- ASOS UK fast-fashion data, September–November 2021.
- Final processed training: 939,537 events.
- Final processed test: 858,526 events.
- 1,084,504 users.
- 338,076 product variants.
- Return:keep ratio ≈ 1.2:1.
- Training uses September–October; test uses October–November.

Graph:
- Bipartite customer–product graph.
- Customer and product are node types.
- Keep/return events are edges.
- Returned edge = 1; kept edge = 0.
- Prediction is edge-level classification.

Customer features include age/year of birth, gender, shipping country, membership, sales count, return count, customer return rate, and proportions of historical return reasons.

Product features include variant/product/supplier IDs, product type, brand, average price, average discount, sales, returns, product return rate, and historical return-reason proportions.

---

## 3. Returnformer Architecture

Pipeline:

**Node2Vec structural embeddings → attention feature fusion → Graph Transformer → Graph External Attention (GEA) → KAN decoder → edge return probability**

### Node2Vec
Purpose: recover global topological information that may be lost when a large interaction graph is partitioned into smaller subgraphs.

Node2Vec controls BFS/DFS behavior with `p` and `q`.

### Attention fusion
Original features and Node2Vec structural features are linearly transformed and assigned learned attention weights, then fused into one node representation.

Conceptually:
`fused = attention(original) + attention(structural)`

### Graph Transformer
Self-attention operates inside each sampled subgraph to capture long-range customer–product dependencies.

The paper's implementation:
- 2 Graph Transformer layers.
- 4 attention heads.
- Edge-feature processing removed.
- Attention logits clamped to [-5, +5] before softmax.
- Residual connections + LayerNorm + 2-layer GELU feed-forward network.

### Graph External Attention (GEA)
Problem addressed: subgraph partitioning can destroy relationships between nodes that belong to different subgraphs.

GEA uses external learnable key/value units ("virtual nodes") so current subgraph node representations can incorporate global/inter-subgraph patterns.

Paper setting:
- 20 external virtual nodes.
- 1 GEA attention head.

### KAN decoder
KAN is used for link classification rather than a standard shallow MLP/inner-product decoder.

KAN learns trainable univariate functions, implemented with B-spline functions, to model nonlinear decision boundaries.

---

## 4. Paper Results

Returnformer:
- Accuracy: 75.04%
- Precision: 72.29%
- Recall: 86.75%
- F1: 78.87%
- AUC: 84.42% (0.844)

Returnformer beat the seven comparison models on all reported metrics except precision.

Comparison families:
- MLP
- XGBoost
- LightGBM
- CatBoost
- GCN
- GAT
- GraphSAGE

GraphSAGE itself achieved F1 = 77.41%, the highest F1 among the comparison baselines.

High-return-customer subset (customer return rate >= 50%):
- Accuracy: 79.23%
- Precision: 80.80%
- Recall: 95.71%
- F1: 87.63%
- AUC: 78.21%

The paper's PR analysis reports Average Precision (AP) = 0.865.

Important paper interpretation:
- Recall is high relative to precision.
- The authors frame return prediction as risk-sensitive.
- The output is a continuous probability; threshold can be changed according to business tolerance.
- The paper suggests interventions such as reminders, size recommendations, more product information, and freight adjustments.

---

## 5. Project-Specific Return GNN Experiment

The reproduction used the same broad customer–product graph idea but deliberately tested complexity incrementally.

Key data facts:
- Graph is extremely sparse: ~1.1 edges per node.
- ~78% of test customers are unseen during training (cold-start).
- Cold-start performance is therefore treated as especially important for deployment.

Experimental sequence:
1. Tabular baseline: XGBoost, LightGBM, CatBoost, MLP.
2. Bipartite graph + GraphSAGE.
3. Graph Transformer.
4. Graph Transformer + Node2Vec.
5. Graph Transformer + Node2Vec + attention fusion.

### Project results

| Model | Overall AUC | Cold-customer AUC | Interpretation |
|---|---:|---:|---|
| Best tabular baseline | 0.833 | ~0.65 | Reference floor |
| GraphSAGE | **0.876** | **0.767** | Best model built |
| Graph Transformer | 0.874 | 0.761 | No gain over GraphSAGE |
| GT + Node2Vec (concat) | 0.859 | 0.701 | Degraded |
| GT + Node2Vec + Fusion | 0.864 | 0.689 | Degraded |

F1 scores clustered around 0.73–0.78 at an untuned 0.5 threshold.

### Main project conclusion
The project evidence says the **simple GraphSAGE model captures the useful graph signal**, while the additional components from Returnformer did not improve this particular sparse dataset.

GraphSAGE:
- Overall AUC: 0.876.
- Cold-customer AUC: 0.767.
- It captures the full observed graph benefit.
- It avoids a separate Node2Vec embedding-training step.
- It is cheaper and better aligned with latency/retraining constraints.

Node2Vec and attention fusion hurt cold-start performance. The project interpretation is that on a sparse, mostly-one-time-customer graph, global topological position is relatively redundant/noisy compared with direct-neighbour information and product/customer features.

This is a **dataset-specific result**, not evidence that Returnformer components are universally bad.

### Why this differs from the paper
The paper uses a large, full-scale graph where partitioning causes substantial structural information loss, so global topology and inter-subgraph information are useful.

The project's graph is deliberately smaller/sparser and has many cold-start customers. In that setting, direct-neighbour message passing appears sufficient and global structural embeddings add noise.

Optional future experiment: use a denser subgraph to directly test the sparsity hypothesis.

---

## 6. AUC vs F1

AUC is the project's primary model-selection metric because:
- AUC evaluates ranking across all thresholds.
- The product's operating threshold is a business decision, not inherently 0.5.
- Brands may choose different thresholds based on intervention costs.
- Different calibration can make F1@0.5 misleading for model comparison.

F1/precision/recall become operating metrics after a brand chooses a threshold.

The project therefore recommends:
- AUC for model selection.
- PR-AUC as an additional ranking metric.
- Precision/recall/F1 at the chosen operating point.

---

## 7. Why GEA and KAN Were Not Implemented in the Project

GEA exists to reconnect information across partitioned subgraphs. The project operates at single-subgraph scale specifically to avoid that partitioning, so GEA has no corresponding role without redesigning the processing setup.

Testing GEA would require processing the full graph and was considered infeasible on available hardware.

KAN was also omitted because:
- The paper's reported KAN benefit is modest (~0.5 F1).
- The project's empirical results showed that added architecture beyond basic GNN was neutral-to-negative.
- The expected payoff did not justify the additional complexity.

---

## 8. RTO Product: MVP

Product: **Pre-Dispatch Return & RTO Risk Engine**

MVP prediction target:
**pre-delivery RTO for COD orders only** — COD refusal/non-acceptance, customer unreachable, failed delivery attempt.

Post-delivery return prediction is out of scope for MVP.

MVP includes:
- Pre-dispatch RTO risk score.
- Ops Risk Dashboard.
- Manual + automated interventions.
- Shopify integration.
- Historical-data backfill.
- Baseline-vs-actual RTO reporting.
- Multi-tenant role-based access.
- Cold-start fallback model.

Out of scope:
- Post-delivery return prediction.
- Full carrier/logistics orchestration.
- Resolve & Recover / Retain & Grow layers.
- Native mobile app.
- Non-Shopify storefronts in MVP.

---

## 9. India RTO Data Adaptation

Reference ASOS data is UK, prepaid-only, fashion-focused. RTO requires India-specific fields.

Key changes:
- `isReturned` → `isRTO`.
- Country → pincode / delivery-zone tier (metro, tier-2, tier-3).
- Add `paymentMethod`.
- Add `courierPartner`.
- Add `promisedDeliveryDate`.
- Add `orderChannel` (app/web/marketplace).
- Add `promoCode`.
- Add `deliveryAttemptCount`.
- `customerReturnRate` / `productReturnRate` → `customerRTORate` / `productRTORate`.
- GBP pricing → INR.
- Keep discount depth as an explicit feature.
- Replace return-reason taxonomy with RTO reasons such as COD refusal, customer unreachable, address/serviceability issue, changed mind at doorstep.

---

## 10. Synthetic RTO Dataset

Synthetic generator is intended for pipeline/architecture validation before real pilot-brand data exists.

Target population parameters:
- Overall RTO rate: ~30%.
- COD share: ~63%.
- Average RTO hard cost: ~₹300.

Synthetic data should preserve realistic correlations, especially between RTO and:
- COD.
- Discount depth.
- Delivery-zone tier.
- Customer RTO history.

Suggested scales:
- ~10K orders for rapid iteration.
- ~500K+ orders for stress testing.

Generator must be versioned and seeded for reproducibility.

Synthetic metrics must **not** be presented as production accuracy claims.

Default synthetic vertical: apparel/fashion.

---

## 11. RTO Production Architecture in PRD

The PRD currently specifies:

**Node2Vec → Graph Transformer → GEA → KAN**

with baseline fallback models:
- XGBoost
- LightGBM
- CatBoost
- MLP

Important project-level caveat:
The return experiments found GraphSAGE superior to the more complex Returnformer-style stack on the sparse return dataset. The RTO PRD still requires ablation testing rather than assuming those return results transfer to RTO.

Therefore the correct interpretation is:
**RTO architecture is a product hypothesis; it must be validated on RTO data.**

Required evaluation:
- Accuracy
- Precision
- Recall
- F1
- AUC
- PR-AUC
- High-RTO customer/product slices
- Ablation of Node2Vec, GEA, and KAN

Threshold is per-brand, based on false-positive vs false-negative cost.

---

## 12. Product Requirements

Functional:
- Synthetic data generator.
- Shopify + courier data ingestion.
- Customer-product graph per brand.
- Scheduled structural embeddings.
- Risk score 0–1 + human-readable contributing reasons.
- Baseline fallback for cold-start customer/product.
- Risk-sorted ops queue.
- Filters and order drill-down.
- Manual overrides.
- Automated threshold-triggered interventions.
- Action/outcome logging.
- Baseline vs actual RTO reporting.
- Role-based multi-tenancy.
- Spike alerts.

Non-functional:
- API scoring target: <300 ms/order, excluding offline embedding refresh.
- Brand-level scalability.
- Hard tenant isolation.
- PII pseudonymisation before graph/model layer.
- DPDP-aligned design.
- Defined uptime SLA.
- Human-readable explanation for every score.
- Documented retraining cadence.

---

## 13. Product Phases

Phase 0:
- Synthetic generator.
- End-to-end pipeline/dashboard validation.

MVP / Pilot:
- COD pre-dispatch RTO engine.
- Graph model + baseline fallback.
- Dashboard + manual override.
- Manual + automated intervention.
- Shopify integration.
- Baseline-vs-actual reporting.
- Recalibration on first real pilot data before go-live.

Phase 2:
- Multi-channel rule builder.
- Explainability.
- Automated billing/metering.
- Analytics/ROI dashboard.

Phase 3:
- Cross-brand pattern sharing / GEA at scale.
- Shopify App Store self-serve.
- Additional storefronts.
- Evaluate real-time session-aware scoring.

---

## 14. Risks

Major risks:
- Synthetic-to-real domain gap.
- Much smaller pilot datasets than the paper.
- Delayed RTO labels.
- Courier API ground-truth reliability.
- DPDP compliance.
- Shopify webhook reliability.

Go-live requires recalibration/revalidation on the first real brand data batch.

---

## 15. Future Real-Time Session-Aware Extension

Not MVP.

MVP scores at order placement using precomputed graph embeddings.

Future extension adds:
- Click events.
- Search.
- Product-detail-page views.
- Price exploration.
- Click count.
- Distinct SKUs viewed.
- Price range explored.
- Category switches.
- Dwell time.

The live session vector becomes a third input alongside original + structural features.

Risk can be recomputed at:
**PDP view → add-to-cart → checkout**

Additional infrastructure:
- Client-side event capture.
- Low-latency session-state store (Redis-class).
- Cold-start path using product embedding + session vector + baseline model.

Early accuracy must be treated as unvalidated and A/B tested before operational reliance.

---

## 16. Critical Source Distinctions

### Paper vs project experiment
Paper result: Returnformer AUC ≈ 0.844.
Project result: GraphSAGE AUC = 0.876 and cold-start AUC = 0.767.

Do not quote the paper's 0.844 as the project's result.

### Return vs RTO
Return: post-delivery return/keep outcome.
RTO: pre-delivery non-acceptance/non-delivery, especially COD in the MVP.

Do not silently merge these labels.

### Synthetic vs real accuracy
Synthetic RTO results are for pipeline/architecture validation, not production accuracy.

### Returnformer architecture vs validated project architecture
The paper proposes Node2Vec + Graph Transformer + GEA + KAN.
The project's sparse-graph experiment found GraphSAGE best.
The RTO PRD still proposes the Returnformer-style stack but explicitly requires ablation on RTO data before assuming its components help.
