# Checkpoint — India Synthetic Pipeline: Validation, Positive Control & Model Decision

Companion to `PROJECT_HANDOFF.md`, `india_schema_map.md`, and `project_roadmap.md`.
Covers everything from the exact-schema generator rebuild through the final
graph-vs-tabular decision. This closes out **Phase 0** of the roadmap.

---

## 1. Status

**Phase 0 (pipeline validation on synthetic India data): COMPLETE.**
Decision made: **tabular gradient-boosted models (XGBoost/CatBoost), not GraphSAGE,
are the production model for pre-dispatch RTO scoring.** This is not a default —
it followed two fair comparisons at different scales, a realism audit against
real industry benchmarks, and a purpose-built positive control that found and
fixed two real bugs before being trusted. See §6 for the full reasoning.

Still open: professor's reply on the Shopify label question (Option 1 vs 2 —
see prior thread), which gates Phase 0.3 (real Shopify integration).

---

## 2. Schema rebuild — exact drop-in compatibility

The generator was rebuilt to emit the user's **real** column names/counts,
confirmed by direct inspection of the local pickles (not the PRD's nominal
30/44 — actual is **31 customer cols, 42 product cols, 3 event cols**), with
identical filenames (`customer_nodes_training.p`, etc.). Verified via set
equality: customer 31/31, product 42/42, event 3/3. Result: the synthetic data
runs through every existing pipeline script (`profile_data.py` →
`build_features.py` → `train_baselines.py` → `sample_subgraph.py` →
`build_graph.py` → `train_gnn.py`) with **zero script edits**.

Key semantic notes carried in `india_schema_map.md`:
- `isReturned` now means **RTO** (pre-delivery non-acceptance), not post-delivery return.
- `Country_A/B/C` repurposed as metro/tier-2/tier-3 one-hots; `Country_D–I` are
  structurally present but always zero (only 3 India zone tiers vs 9 UK countries).
- `avgGbpPrice` holds **INR** values under the old GBP-era name (kept for pipeline compatibility).
- The 13-code `*_return_code_*` taxonomy is **modeled, not data-derived** — chosen
  to match the reference paper's shape, then relabeled to India RTO reasons.
- `event_india_extra.p` — a side file — carries the India-only order fields
  (COD, courier, zone tier, channel, promoCode, deliveryAttemptCount,
  promisedDeliveryDate) not present in the base 3-column event schema.

---

## 3. Calibration — validated against the PRD's Section 8.2 rules

At 10K-order scale (seed 42): overall RTO 0.31 (target 0.30), COD share 0.64–0.65
(target 0.63), RTO|COD 0.44 vs RTO|prepaid 0.075 (ratio 5.86×), tier gradient
metro 0.25 → tier2 0.34 → tier3 0.44–0.46, cold-start test-customer fraction 0.71
(target ~0.70), edges/customer 1.80. All four of the PRD's explicit synthetic-field
rules (§8.2 table) implemented and confirmed. Leakage-safety validated: the
customer-rate feature's single-feature AUC is 0.59–0.61 on held-out **test**
labels (genuine signal, not the label in disguise).

---

## 4. Pipeline runs — chronological results

| Run | Scale | Features | Best baseline overall AUC | Best baseline cold AUC | GraphSAGE overall AUC | GraphSAGE cold AUC |
|---|---|---|---|---|---|---|
| 1 | 10K | no COD | 0.646 (LightGBM) | 0.599 (LightGBM) | 0.622 | 0.594 |
| 2 | 500K | no COD | 0.633 (XGBoost) | 0.605 (approx., XGBoost) | 0.615 | 0.610 |
| 3 | 500K | **+ COD/tier/courier** | **0.691 (XGBoost)** | **0.726 (XGBoost)** | 0.657 | 0.665 |
| 4 (positive control) | 500K, density=6, injected graph signal | + COD/tier/courier | 0.803 (CatBoost) | 0.770 (CatBoost) | 0.739 | 0.683 |

**Run 1→2 (10K→500K, no COD):** scale alone did not change the picture —
baseline and GraphSAGE stayed roughly tied at both scales. Ruled out "not enough
data" as the explanation.

**Run 2→3 (adding COD/tier/courier as real features):** the single highest-value
change in the whole project. Cold-customer AUC jumped **+0.12 to +0.15** across
every model (XGBoost 0.605→0.726, LightGBM 0.601→0.719, CatBoost 0.606→0.721,
MLP 0.577→0.650) — because COD had been present only in the causal label logic
and a side file, never in the feature matrix build_features.py actually used.
Root cause + fix documented in §5.

**Run 3 — the fair, real-data-relevant rematch:** with both models given
identical access to COD/tier/courier, GraphSAGE still lost on every slice
(overall −0.034, cold −0.061). This is the number that matters for the
production decision — it reflects honest, uninjected RTO drivers.

**Run 4 — positive control (see §6):** deliberately injected graph-only signal,
raised graph density, gave the GNN every fair/favorable condition. Still lost,
including on cold-start. Absolute numbers in this row are not comparable to
runs 1–3 (different label distribution, different density) — only the
*relative* finding (tabular > GraphSAGE) is the takeaway.

---

## 5. Bugs found and fixed this phase

| # | Where | Symptom | Root cause | Fix | Verified |
|---|---|---|---|---|---|
| 1 | `train_gnn.py` | Printed a fixed "compare to ~0.833 / ~0.65" regardless of dataset | Hardcoded ASOS-run numbers in a print statement | Read `baseline_results.csv` from the current run instead; degrade gracefully if absent/malformed | Unit-tested against a real CSV shape; correctly picks best model + AUC |
| 2 | (not a bug) `train_baselines.py` leakage probe | Showed AUC 0.95 for `customerReturnRate`, looked like leakage | Probe runs train-vs-train; at low orders/customer, many customers have exactly 1 train order, making the "check" near-circular | None needed — probe is doing what its docstring says. Documented as a known small-scale artifact | Reproduced the 0.954 exactly; confirmed the real (train→test) check reads 0.605, healthy |
| 3 | `build_features.py` | Cold-customer AUC stuck ~0.60 across all models and both scales | COD/courier/tier lived only in `event_india_extra.p` and the label logic, never joined into the model's feature matrix | Added `load_india_order_features()`: joins `ord__*` columns (COD flag, zone tier, courier, channel, promoCode) from the side file; excludes `deliveryAttemptCount` (label leak: `1 + isRTO*rand`) and the raw promised-delivery date | A/B tested: cold AUC 0.604→0.743 in sandbox; confirmed 0.605→0.726 on the real 500K run |
| 4 | `india_synth_generator.py` (positive-control addition) | Injected "graph-only" relational signal correlated 0.549 with the customer's own latent proneness (should be ~0) | Naive `groupby(product).transform("mean")` includes each row's own value in its own group average; with ~16 orders/product, self-contribution dominates | Leave-one-out aggregation: `(group_sum − self) / (n − 1)` | Correlation with own proneness: 0.549 → **−0.009**. Correlation with the label held at 0.309 (signal preserved) |
| 5 | `sample_subgraph.py` | At density=6, connected-subgraph grower produced exactly 400 products (= `n_seed_products`) regardless of the 100,000-edge target | Stop condition used OR (`isin(products) \| isin(customers)`) but the final subgraph was built with AND — at higher density, OR-count inflates fast enough to trigger the stop before `chosen_products` ever grows past the seed set | Changed the stop check to use the same AND condition as the final result | Reproduction test: OR-logic stuck at 400 products/1 iteration; AND-logic reached 6,608 products/2 iterations under identical conditions. Real re-run: 30,490 products, 82,404 customers |

Bug 5 is a **latent, permanent fix** — it didn't bite at density=1.8 (Runs 1–3)
by chance, not because it wasn't present. Applies to all future runs.

---

## 6. Realism audit — is the synthetic data actually representative?

Cross-checked against the ClickPost playbook (already in project files) and,
for the contested numbers, independent public sources.

| Dimension | Real benchmark | Our data | Verdict |
|---|---|---|---|
| COD/prepaid RTO ratio | ~7×, healthy band 5–10× (ClickPost "Cut A") | 5.86× | ✅ Match |
| Overall RTO (apparel, COD-heavy) | 21–32% | ~30–31% | ✅ Match |
| AOV effect shape | U-shaped, lowest mid-cart | Confirmed (asymmetric U) | ✅ Match |
| Reason: COD refusal | 28–38% of RTOs | 27.6% | ✅ Match |
| Reason: fake/fraudulent | 6–12% | 8.8% | ✅ Match |
| Carrier×tier gap (T2/T3) | 20–25pp | 8.6pp → **fixed to 22.7pp** | ✅ Fixed |
| Reason: address-quality | 18–26% | ~6–11% | ❌ Underweighted (known gap, not fixed — affects only diagnostic reason-code columns, not the label) |
| Reason: customer unreachable | 14–20% | 8.9% | ❌ Underweighted (same, not fixed) |
| Reason: carrier service failure | 5–10% | 0% (no such code) | ❌ Missing entirely (same, not fixed) |
| First-order decay curve | Gradual 29%→22% over orders 1–10 | Binary order-1-vs-rest flag only | ⚠️ Simplified |

**Important caveat, stated explicitly for the write-up:** all real benchmark
figures trace to a single vendor source (ClickPost). Independent public sources
confirm the *direction and order of magnitude* (COD ≫ prepaid, real courier/tier
variance) but show wider variance in absolute numbers (COD RTO reported as low
as 15–30% and ratios as low as 1.5–5× elsewhere). Our calibration sits at the
**upper end of a plausible range**, not a settled consensus figure.

---

## 7. Positive control — full methodology and conclusion

**Motivation:** the fair-comparison result (Run 3) risked being circular — the
label was built entirely from per-order/per-customer factors with no relational
term, so a GNN's inability to win could simply reflect "we never gave it
anything relational to find," not "RTO lacks graph structure."

**Design:** added `graph_signal_strength` (injects a two-hop co-purchase risk
term — a customer's risk depends on the latent risk of *other* customers who
buy the same products) and a `density` override, both CLI-exposed and
default-off (honest data unaffected).

**Result after fixing bugs #4 and #5 (Run 4, §4):** GraphSAGE still lost,
including on cold-start (0.683 vs best baseline's 0.770).

**Diagnosis — two mechanistic reasons, not a shrug:**
1. The injected signal, once leave-one-out-corrected to be independent of a
   customer's own latent trait, is still a **customer-level constant** (same
   value on every order that customer places). For **warm** customers, any
   such constant effect is automatically visible through their own historical
   RTO rate — which the tabular model already has. This makes warm-customer
   performance an unfair test of graph vs. tabular regardless of signal origin.
2. **Cold customers get zero training-period edges by definition.**
   `train_gnn.py` builds the message-passing graph from `train_mask` edges
   only; a cold customer's node embedding is computed with no neighbors,
   entirely before the decoder ever sees which product their test-period order
   is for (the test edge is only used at decode time, after embeddings are
   frozen). The architecture cannot let a cold customer's embedding reflect
   anything about their specific order — this would be true regardless of how
   much real-world graph signal exists.

**Conclusion:** this is not evidence that RTO lacks graph structure — it is
evidence that this specific inductive, train-only-message-passing GraphSAGE
**cannot exploit relational signal for cold-start customers by construction**,
which is exactly the population the product needs to serve. A fix exists
(semi-inductive graph construction using test-edge *topology*, not labels, at
message-passing time) but is a materially larger rebuild, named here as future
work and explicitly not pursued given the practical answer (use the tabular
model) is unaffected either way.

**Decision: XGBoost/CatBoost on order + node features is the production model.**
This also better fits the PRD's own non-functional requirements (near-real-time
scoring, explainability for ops teams) than a graph-serving stack would.

---

## 8. Threshold tuning

Built `tune_threshold.py`: sweeps decision thresholds, reports precision/recall/F1
overall and on the cold slice, and a rupee cost model (₹300/missed RTO,
₹40/challenged good order, both configurable).

**Finding:** on the real 500K COD-feature set, cold-customer recall collapses to
0 above threshold ≈0.10–0.25 and stays there through 0.90 — cold-order
probabilities cluster in a narrow low range. A single global threshold serves
the cold segment poorly. Extended the sweep to finer/lower thresholds
(0.01–0.09) and added a **cold-segment-specific best-F1 threshold**,
recommended as a separate cutoff for `customer_no_history=1` orders rather
than one global cutoff for everything.

---

## 9. Artifacts produced this phase

- `india_synth_generator.py` — exact-schema generator; `--graph-signal`,
  `--density` knobs; courier realism fix baked in.
- `build_features.py` — patched to fold in India order-level features.
- `build_graph.py` / `train_gnn.py` — patched to carry `ord__*` as edge
  attributes; `train_gnn.py` also fixed for dynamic baseline comparison.
- `sample_subgraph.py` — patched for the OR/AND stop-condition bug.
- `tune_threshold.py` — new; threshold sweep + cost model + cold-segment recommendation.
- `india_schema_map.md` — column-provenance reference (real / derived / modeled).
- `project_roadmap.md` — overall Level B plan and phasing.

---

## 10. Next steps

1. **Blocked, waiting:** professor's reply on the Shopify label question
   (real features + generated label, vs. a real proxy label like cancellations).
2. **Unblocked:** re-run `tune_threshold.py` with the extended grid on the real
   500K set; adopt a cold-segment-specific threshold in the eventual scoring service.
3. **Unblocked:** fold this checkpoint + the findings memo into the project
   writeup; the graph-vs-tabular question is closed for this project's scope.
4. **Deferred, per earlier plan:** scoring API, dashboard, rules engine — hold
   until the Shopify ingestion path (Phase 0.3) is settled, since that decides
   the final feature set the served model trains on.
