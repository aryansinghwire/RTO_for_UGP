# Pre-Dispatch Return / RTO Risk Engine — Checkpoint: Phase 0 & Phase 1

**Status:** Phase 0 and Phase 1 complete. Phase 2 (bipartite graph construction) not yet started.
**Purpose of this document:** a working technical record, not final presentation copy. Captures the
data, the decisions, the reasoning behind them, and the results — so they don't have to be
reconstructed from memory once Phase 2/3 are underway. Intended to be extended as later phases
complete, then adapted into presentation form at the end.

---

## 1. Project Context

Reproducing the architecture from Cao, Zhang & Li, *"Returnformer: A Graph Transformer-Based Model
for Predicting Product Returns in E-Commerce"* (Entropy, 2026), per the internal PRD *"Pre-Dispatch
Return & RTO Risk Engine."* The paper predicts product returns before payment using a customer–
product bipartite graph, a Graph Transformer encoder, a custom Graph External Attention (GEA)
mechanism for cross-subgraph pattern sharing, and a Kolmogorov–Arnold Network (KAN) decoder.

Working from real ASOS UK fast-fashion data: six pickle tables (event / customer-node /
product-node, each split train / test), the same dataset family the paper itself trains on.

The eventual PRD target is an India D2C RTO-risk scoring engine; this build phase works on the
paper's original ASOS/return-prediction task first, as a faithful reproduction, before any
India-specific adaptation.

---

## 2. Phase 0 — Data Profiling & Cleaning

### 2.1 Initial profile

All six tables loaded successfully and matched the PRD's Section 7 schema on first inspection:
event tables at 3 columns, customer-node tables at 30 columns, product-node tables at 44 columns.
Raw scale (pre-cleaning):

| Table | Rows | Cols |
|---|---|---|
| event_train | 1,369,133 | 3 |
| event_test | 1,460,366 | 3 |
| customer_train | 777,001 | 30 |
| customer_test | 825,598 | 30 |
| product_train | 411,495 | 44 |
| product_test | 411,544 | 44 |

Label balance (raw): train 1.24:1 return:keep, test 1.20:1 — consistent with the paper's reported
~1.2:1, no material class imbalance.

### 2.2 Data-quality issues found and resolved

Three defects surfaced during profiling, all specific to this export (not described in the
paper's methodology, and not general properties of the underlying data):

1. **Duplicate reason-code column.** Both customer and product node tables carried a repeated
   column name (`..._level_return_code_D` appearing twice, holding different data). Diagnosed via
   a targeted check: listing the real column names showed A, B, C, D, E, **D**, F, G, H, I, J, K, L
   — every letter A–L present plus a second D. The paper's Figure 2 lists **thirteen** distinct
   return-reason categories (the PRD's Section 7 undercounted this as twelve). Conclusion: this is
   a genuine 13th category mislabeled with a repeated letter, not a duplicate/redundant column.
   **Fix:** renamed the second occurrence to `_M` in all four node tables. Verified post-fix: all
   13-column reason-code families sum to 1.000 across 100% of rows in both customer and product
   tables — confirming a real, complete taxonomy, nothing dropped or double-counted.

2. **Leftover raw string columns.** The product table retained raw text `productType` and
   `brandDesc` columns alongside their already-one-hot-encoded equivalents (`productType_*`,
   `Brand_*`). Redundant, and non-numeric columns of this kind broke a downstream aggregate check
   (crashed the profiler once before this was found). **Fix:** dropped the two raw string columns;
   kept the one-hot families, which is what model training needs.

3. **Age derivation.** Added `age = 2021 - yearOfBirth` per the paper's Section 3.1.2. Not dropped
   at this stage — implausible ages are handled downstream (see 2.3 and 2.4), not silently removed
   here.

### 2.3 Paper-fidelity cleaning: what we replicated, and what we couldn't

The paper's documented cleaning (Section 3.1.2) consists of two steps: deduplicate rows, and
exclude customers over 90 years old (and, implicitly, their events — final event counts drop
accordingly). Both were implemented as an explicit, separately-logged stage (kept distinct from
the artifact fixes above, since this one is a scope decision affecting which real data enters the
model, not a bug fix):

| | Train | Test |
|---|---|---|
| Raw | 1,369,133 | 1,460,366 |
| Exact duplicate rows removed | 6,551 (0.48%) | 7,223 (0.49%) |
| Events from excluded (>90yo) customers removed | 18,670 (1.36%) | 20,694 (1.42%) |
| Conflicting-label pairs found (same customer+product, different label) | 3,699 — flagged, **not removed** | 3,883 — flagged, **not removed** |
| **Final** | **1,343,912** | **1,432,449** |
| vs. paper's reported count | 939,537 → **+43.0%** | 858,526 → **+66.8%** |

Conflicting-label pairs were deliberately not resolved: the event table has no order ID or
timestamp, so there is no way to determine whether a repeated (customer, product) pair with
different labels is a genuine repeat purchase (bought twice, kept once/returned once) or an export
artifact. Guessing risks destroying real signal; this is documented as a known schema limitation
rather than silently patched.

**Why the gap remains after replicating both documented steps:** the paper's own numbers are
informative here. Its raw dataset is described as "approximately 1.8 million events," and its
final cleaned counts sum to 1,798,063 — i.e. the paper's own cleaning removed only a small
fraction of its raw data. Our raw total (2,829,499) is ~57% larger than the paper's ~1.8M *before
any cleaning at all*. The two documented cleaning steps combined removed under 2% of our raw data
— nowhere near enough to explain the gap. The duplicate-row hypothesis was tested directly and
rejected (only 0.48–0.49% of rows were exact duplicates). **Conclusion: this export is a
genuinely different data vintage/pull than the one the paper worked from, not a preprocessing gap
on top of the same underlying data.** Documented as such rather than force-subsampling to match
the paper's headline figures, which would misrepresent the method.

### 2.4 Structural findings (drive later architecture decisions)

Two findings from Phase 0 turned out to be the most consequential facts about this dataset —
more load-bearing for later design decisions than the row-count discrepancy above.

**Orphan edges (join-key integrity).** A large share of events reference a customer or product
with no corresponding row in the node tables:

| | Train | Test |
|---|---|---|
| Customer-side orphans | 71,197 (5.30%) | 74,559 (5.21%) |
| Product-side orphans | 465,772 (34.66%) | 443,216 (30.94%) |

Root-caused via a targeted diagnostic rather than assumed: `returnsPerProduct` (and
`returnsPerCustomer`) have a **minimum value of 1** across both node tables — i.e. the node tables
only contain entities with at least one historical return. 193,666 distinct orphan variant IDs
were confirmed genuinely absent from the product node table (not a hash/join bug — a broken join
would fail far more than the observed 30–35%). Checked for the obvious risk this implies — that
node-table presence correlates with the label, which would bias any model that dropped orphans —
and found no such bias: orphan edges return at 55.4% vs. 55.2% for resolved edges, statistically
indistinguishable. **Decision: orphans are imputed, not dropped** — both because dropping would
discard a third of the data for no accuracy benefit, and because the PRD explicitly requires
cold-start orders (which an orphan effectively is) to be scored, not skipped.

**Cold-start overlap (train/test entity overlap).**

| | In train | In test | Test-only (cold-start) |
|---|---|---|---|
| Customers | 764,725 | 812,220 | 630,519 (**77.6%**) |
| Products | 411,495 | 411,544 | 6,039 (**1.5%**) |

This asymmetry is the single most architecturally consequential number from Phase 0. The customer
base is overwhelmingly cold at test time; the product catalog is almost entirely stable
month-to-month. This reframes the whole problem: any model's ability to handle **unseen
customers** — not unseen products — is what determines real-world performance, since 78% of test
traffic falls into that bucket.

---

## 3. Phase 1 — Feature Engineering, Evaluation Harness, Baseline Models

### 3.1 Feature build

One row per event, built by left-joining each edge to its customer and product node features.
Orphan (no-history) endpoints are imputed rather than dropped, using a rule keyed to column role
rather than a single blanket strategy:

| Column role | Examples | Imputation |
|---|---|---|
| Rate | `customerReturnRate`, `productReturnRate` | Mean of that split's own node table |
| Count / reason-proportion | `salesPer*`, `returnsPer*`, `*_return_code_*` | Zero (no history = no counts) |
| Continuous descriptive | `age`, `avgGbpPrice`, `avgDiscountValue` | Mean (zero is implausible for these) |
| Binary / one-hot | `Country_*`, `Brand_*`, `productType_*`, `isMale`, `premier` | Zero (unknown category) |

Explicit `customer_no_history` and `product_no_history` flags are added so downstream models can
learn to treat imputed rows differently — this is what makes the cold-start evaluation split (3.2)
possible, and what the resulting models are shown (3.4) to actually use.

Final feature tables: **train 1,343,912 × 75 cols (70 model features)**, **test 1,432,449 × 75**.

### 3.2 Evaluation harness (reusable across all remaining phases)

A shared scoring module (`eval_harness.py`) implemented once so every model — baseline through the
eventual Graph Transformer — is scored identically:

- Standard set: Accuracy, Precision, Recall, F1, AUC, PR-AUC (matches the paper's own metric
  choices in Figures 8/9/12).
- **High-return-customer slice** — reproduces the paper's Table 4 pattern (metrics restricted to
  customers with ≥50% historical return rate).
- **Cold-start split** — metrics computed separately for warm (real history) vs. cold (imputed)
  edges, on both the customer and product side. Not something the paper needed (it doesn't report
  cold-start behaviour), but essential here since the PRD's cold-start fallback model is judged on
  exactly this split.
- **Leakage probe** — single-feature ranking AUC (no model fit required) for the return-rate
  columns, to check whether they were computed using information from the window being predicted.

### 3.3 Baseline models

Four tabular baselines, matching both the paper's comparison set (Section 4.2) and the PRD's
required cold-start fallback models (Section 9): XGBoost, LightGBM, CatBoost, and an MLP. Trees
trained on the full 1,343,912-row training set; the MLP was capped at 200,000 training rows
(documented limitation — sklearn's MLP has no practical minibatch/GPU path at this scale; all
models were evaluated against the full 1,432,449-row test set regardless). No hyperparameter
search was performed (the paper uses Optuna); reasonable defaults only — sufficient for a
comparison baseline, not a tuned final model.

### 3.4 Results

**Overall test-set metrics, full data:**

| Model | Accuracy | Precision | Recall | F1 | AUC | PR-AUC |
|---|---|---|---|---|---|---|
| XGBoost | 0.7492 | 0.7565 | 0.7972 | 0.7763 | 0.8329 | 0.8597 |
| LightGBM | 0.7489 | 0.7519 | 0.8059 | 0.7780 | 0.8324 | 0.8593 |
| **CatBoost** | 0.7495 | 0.7571 | 0.7968 | 0.7764 | **0.8332** | 0.8598 |
| MLP (200K-row cap) | 0.7465 | 0.7500 | 0.8034 | 0.7758 | 0.8293 | 0.8551 |

**Leakage probe:** `customerReturnRate` single-feature AUC = 0.801, `productReturnRate` = 0.634.
Full models reach ~0.83 AUC — a clear margin above the strongest single feature, confirming the
model is combining signal across features rather than one column dominating. Read as genuine
signal, not a leakage artifact.

**Cold-start split (customer side), consistent across all four models:**

| | Warm AUC | Cold AUC | Gap |
|---|---|---|---|
| XGBoost | 0.8388 | 0.6477 | −0.191 |
| LightGBM | 0.8382 | 0.6504 | −0.188 |
| CatBoost | 0.8391 | 0.6499 | −0.189 |
| MLP | 0.8350 | 0.6391 | −0.196 |

**Cold-start split (product side), consistent across all four models:**

| | Warm AUC | Cold AUC | Gap |
|---|---|---|---|
| XGBoost | 0.8462 | 0.8008 | −0.045 |
| LightGBM | 0.8456 | 0.8004 | −0.045 |
| CatBoost | 0.8466 | 0.8007 | −0.046 |
| MLP | 0.8417 | 0.7992 | −0.043 |

### 3.5 Key findings

1. **The leakage question is resolved.** The gap between single-feature AUC (0.80) and full-model
   AUC (0.83+) is real and consistent — the return-rate features are strong and legitimate, not
   contaminated with future information.

2. **Model agreement validates the pipeline, not any one algorithm.** Four independent algorithms
   converge to within 0.004 AUC of each other. This is stronger evidence the data/feature
   pipeline is sound than any single model's score would be — a bug in one model's setup would
   show up as an outlier, and none appeared.

3. **Cold-start is a customer problem, not a product problem — and this holds across every
   model tested.** The ~0.19 AUC customer warm/cold gap vs. the ~0.045 product warm/cold gap,
   reproduced identically by four different algorithms, is the strongest single finding from
   Phase 1. It reframes the project's central technical question: does adding graph structure
   help specifically with unseen customers (who, via the bipartite graph, still connect to
   products with known return patterns), given that 78% of real test traffic is exactly this
   case?

4. **Baseline floor established: ~0.833 AUC / ~0.777 F1** (CatBoost marginally best, though the
   four are close enough to be considered tied). This is the number Phase 3's graph model must
   clear to justify the architecture's added complexity — the comparison this whole project is
   ultimately structured around.

5. **Sanity check against the paper.** The paper's own tabular baselines land in the 0.80–0.83
   AUC range. Landing in the same range, on different (larger, differently-vintaged) data,
   is a meaningful cross-check that nothing is structurally broken in the reproduction.

---

## 4. Engineering Artifacts Produced

| File | Purpose |
|---|---|
| `profile_data.py` | Phase 0 profiler — schema detection, join-key integrity, cold-start overlap, reason-code sanity, duplicate-column detection. Hardened to never crash mid-run (every section wrapped, report always saved). |
| `clean_data.py` | Two-stage cleaning: (1) artifact bug-fixes, always on; (2) paper-fidelity stage (dedupe, age-exclusion), toggleable, logged separately, reports final counts against the paper's reference figures. |
| `build_features.py` | Joins events to node features with role-aware orphan imputation and `_no_history` flags. |
| `eval_harness.py` | Shared, reusable scoring module — metrics, high-return slice, cold-start split, leakage probe. Used unchanged by every model from here forward. |
| `train_baselines.py` | Trains/evaluates the four baselines. Supports selecting a subset of models and a fast dry-run row cap, so a pipeline check doesn't require a full-data run. |

---

## 5. Documented Deviations from the Paper (for transparency)

- **Dataset scale**: ~1.34M/1.43M final events vs. the paper's reported 939,537/858,526. Traced to
  a different data export vintage, not a preprocessing gap — the two cleaning steps the paper
  documents account for under 2% of the difference once replicated here.
- **No order-level key** in the event table — a small number of same-customer/same-product event
  pairs carry conflicting labels and cannot be safely deduplicated or resolved; flagged and left
  in rather than guessed at.
- **Reason-code taxonomy is 13 categories**, matching the paper's Figure 2 exactly once the
  duplicate-column defect was fixed (the PRD's Section 7 description undercounted this as 12).
- **No hyperparameter tuning** applied yet (paper uses Optuna) — baselines use reasonable defaults;
  tuning deferred as a refinement, not required to validate the pipeline.

---

## 6. Next: Phase 2 Preview

Phase 2 begins bipartite graph construction. Scoped deliberately smaller than the paper's
full-scale, partitioned approach: a subgraph of roughly 20,000–50,000 events (plus every customer
and product touching them), small enough to hold in memory as a single connected graph rather than
partitioning it. This is a considered simplification with a direct architectural consequence: Graph
External Attention (GEA) exists in the paper specifically to reconnect information across
partitioned subgraphs — at single-subgraph scale it has nothing to reconnect, so it is deferred to
an optional stretch tier rather than treated as required. The KAN decoder is deferred alongside it
(the paper's own ablation shows both contribute a modest ~0.5–0.6 F1 each on top of the core
architecture). The required Phase 3 target is the core of the paper's method — Node2Vec structural
embeddings, the attention-fusion module, and a Graph Transformer encoder (via PyTorch Geometric's
`TransformerConv`) — evaluated through the same harness built in Phase 1, benchmarked directly
against the 0.833 AUC baseline floor established above.
