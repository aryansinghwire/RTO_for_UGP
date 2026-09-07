# Pre-Dispatch Return & RTO Risk Engine — RAG-Optimized PRD

## Document status
Draft v0.3. MVP scope locked.
Synthetic dataset plan defined.
Real-time session-aware scoring is a Phase 3+ extension, not MVP.

Primary research input: Cao, Zhang & Li, Returnformer, *Entropy* 2026, 28, 72.

## 1. Product purpose
Build a pre-dispatch order-risk engine and operations dashboard for D2C brands.

The system should identify high-risk orders before dispatch (ideally before payment confirmation), allowing operations teams to intervene before shipping/packaging/reverse-logistics costs are incurred.

## 2. Problem
PRD working assumptions:
- India D2C RTO rate ≈ 30%.
- COD share ≈ 63%.
- Estimated annual RTO/NDR losses ≈ ₹8,000 Cr.
- Hard cost per RTO ≈ ₹300.

Current interventions are largely blanket policies or manual judgement.

## 3. MVP target
**Predict pre-delivery RTO for COD orders.**

RTO includes:
- COD refusal/non-acceptance.
- Customer unreachable.
- Failed delivery attempt.

Post-delivery return prediction is out of MVP scope.

## 4. Users

### Ops Analyst
Needs:
- Prioritized at-risk order queue.
- Risk score.
- Reasons.
- One-click action.

### Ops Manager / Brand Admin
Needs:
- Threshold/rule configuration.
- Intervention configuration.
- Baseline vs actual RTO.
- ROI reporting.

### Support/Admin
Needs:
- Brand onboarding.
- Model-health monitoring.
- Tenant/access management.

## 5. MVP scope

### In scope
- Pre-dispatch COD RTO scoring.
- Returnformer-style graph model + cold-start baseline fallback.
- Risk dashboard.
- Manual + automated interventions.
- Shopify connection.
- Historical backfill.
- Baseline-vs-actual RTO reporting.
- Multi-tenant role-based access.

### Out of scope
- Post-delivery return prediction.
- Full carrier/logistics orchestration.
- Resolve & Recover.
- Retain & Grow.
- Native mobile app.
- Non-Shopify storefronts (Phase 2+).

## 6. Reference data model

The ASOS reference implementation uses three tables: event, customer node, product node.

### Event table
- `hash(variantID)` — product-variant graph endpoint.
- `hash(customerId)` — customer graph endpoint.
- `isReturned` — binary target; 1 returned, 0 kept.

### Customer node
Identity:
- `hash(customerId)`

Demographics:
- `yearOfBirth`
- `isMale`
- `shippingCountry`
- `premier`

Behaviour:
- `salesPerCustomer`
- `returnsPerCustomer`
- `customerReturnRate`

Return-reason profile:
- `customerId_level_return_code_A`–`L`

Geography:
- `Country_A`–`Country_I`

### Product node
Identity:
- `hash(variantID)`
- `hash(productID)`
- `hash(supplierRef)`

Catalog:
- `productType`
- `brandDesc`

Pricing:
- `avgGbpPrice`
- `avgDiscountValue`

Behaviour:
- `salesPerProduct`
- `returnsPerProduct`
- `productReturnRate`

Return-reason profile:
- product-level return-reason codes corresponding to A–L.

Reference scale:
- 939,537 training events.
- 858,526 test events.
- 1,084,504 users.
- 338,076 variants.
- return:keep ≈ 1.2:1.

## 7. India schema adaptation

The ASOS dataset is UK, prepaid-only and return-labelled. It needs structural changes for India RTO.

| Reference | India RTO adaptation |
|---|---|
| `isReturned` | `isRTO` |
| shipping country | pincode / delivery-zone tier |
| no payment field | `paymentMethod` |
| no courier field | `courierPartner` |
| no promised date | `promisedDeliveryDate` |
| no channel field | `orderChannel` |
| no promo field | `promoCode` |
| no attempt count | `deliveryAttemptCount` |
| customer/product return rate | customer/product RTO rate |
| GBP price | INR |
| return reasons A–L | RTO-reason taxonomy |

Suggested RTO reasons:
- COD refusal.
- Customer unreachable.
- Address/serviceability issue.
- Changed mind at doorstep.

RTO taxonomy should be standardized across brands but customizable by brand.

Delivery-zone tier:
- Metro.
- Tier-2.
- Tier-3.

The PRD treats delivery-zone tier as a stronger India RTO signal than country.

## 8. Synthetic data strategy

Purpose: develop and validate the pipeline before real pilot-brand data exists.

Generate:
- Customer table.
- Product table.
- Event table.

Target parameters:
- RTO ≈ 30%.
- COD ≈ 63%.
- RTO cost ≈ ₹300.

Do not sample every field independently. Preserve realistic correlations:
- COD ↔ RTO.
- Discount depth ↔ RTO.
- Delivery-zone tier ↔ RTO.
- Customer RTO history ↔ future RTO.

Scales:
- ~10K orders for fast iteration.
- ~500K+ orders for stress testing.

Version and seed the generator.

**Synthetic results are pipeline/architecture validation only, not production accuracy claims.**

Default synthetic catalog: apparel/fashion.

Synthetic field rules:
- `isRTO`: Bernoulli around 30%, adjusted upward for COD, tier-3, prior RTO.
- `paymentMethod`: ~63% COD / 37% prepaid.
- `deliveryZoneTier`: metro/tier-2/tier-3, with tier-3 higher RTO.
- `customerRTORate`: correlated with repeat-customer behaviour.
- `avgDiscountValue`: higher discount depth correlated with higher RTO.
- `productType`, `brandDesc`: representative catalog distribution.

## 9. Functional requirements

### Synthetic Data Generator
Configurable, schema-consistent, India-calibrated generator.

### Data Ingestion
- Shopify order/customer/product webhooks.
- Courier delivery/RTO status.
- Historical order backfill.
- Synthetic and real feeds must be swappable without schema change.

### Graph + Feature Store
- Customer-product bipartite graph per brand.
- Scheduled Node2Vec computation, not per request.
- Maintain customer/product feature tables.

### Scoring
- Risk score 0–1.
- Human-readable contributing reasons.
- Before dispatch, ideally before payment.
- Baseline fallback (XGBoost/LightGBM/CatBoost) for graph cold-start.

### Dashboard
- Risk-sorted order queue.
- Product/cohort/geography filters.
- Customer/product history.
- Manual override.
- Action logging.

### Intervention Rules
- Manual and automated threshold-triggered actions.
- Log action + outcome.

### Reporting/Billing
- Per-brand baseline RTO.
- Monthly improvement delta.
- Outcome-linked billing feed.

### Admin
- Brand onboarding.
- Role-based access.
- Configuration audit log.

### Alerts
Alert when product/cohort RTO/return rate spikes above historical baseline.

## 10. Non-functional requirements

- API scoring latency: <300 ms/order, excluding offline embedding refresh.
- Brand-level scalability without re-architecture.
- Hard tenant data isolation.
- DPDP-aligned handling.
- PII pseudonymised before graph/model layer.
- Defined API/dashboard uptime SLA.
- Human-readable explanation for every score.
- Documented retraining cadence.

## 11. Model/evaluation plan

PRD architecture hypothesis:
**Node2Vec → Graph Transformer → GEA → KAN**

Production baselines:
- XGBoost.
- LightGBM.
- CatBoost.
- MLP.

Evaluate per brand:
- Accuracy.
- Precision.
- Recall.
- F1.
- AUC.
- PR-AUC.
- High-RTO customer/product slices.

Required ablation:
- Node2Vec augmentation.
- Graph-level attention / GEA.
- KAN decoder.

Do not assume the paper's ablation transfers to RTO.

Threshold:
- Tunable per brand.
- Depends on cost of false positive vs false negative.
- PRD notes recall may be more important where missed RTO is more costly.

## 12. Release plan

### Phase 0
Synthetic generator + end-to-end pipeline/dashboard validation.

### MVP/Pilot
- COD pre-dispatch RTO engine.
- Graph model + baseline fallback.
- Dashboard + manual override.
- Manual + automated intervention.
- Shopify.
- Baseline-vs-actual reporting.
- Recalibration on first real pilot data before go-live.

### Phase 2
- Multi-channel rule builder.
- Explainability.
- Automated billing/metering.
- ROI analytics.

### Phase 3
- Cross-brand pattern sharing / GEA at scale.
- Shopify App Store self-serve.
- Additional storefronts.
- Evaluate real-time session-aware scoring.

## 13. Risks/dependencies

### Synthetic-to-real gap
Synthetic model may not transfer to real brand distribution. Mandatory recalibration/revalidation on first real data batch.

### Cold start
Pilot brands will have far less history than the paper. Synthetic data helps pipeline development but does not replace real recalibration.

### Label latency
RTO outcome arrives after delivery attempts, so labels lag scoring.

### Ground truth
Depends on courier partner API reliability.

### Compliance
DPDP sign-off is required.

### Ingestion
Shopify webhook reliability affects real-time scoring.

## 14. Locked decisions
- MVP target = pre-delivery RTO only.
- MVP build initially uses synthetic data because real brand data is not yet available.
- Manual and automated interventions are both MVP scope.
- RTO reason taxonomy should be standardized across brands but allow brand customization.

## 15. Open questions
- Synthetic catalog vertical flexibility beyond apparel/fashion.
- Exact pilot threshold/cost trade-off.
- Synthetic generator implementation.
- First real pilot onboarding timeline.

## 16. Phase 3+ real-time session-aware extension

Not MVP.

Current MVP:
- Scores at order placement.
- Uses precomputed graph embeddings.

Future:
- Stream click/search/PDP/price-exploration events.
- Build live session feature vector:
  - click count.
  - distinct SKUs viewed.
  - price range.
  - category switches.
  - dwell time.
- Extend original+structural attention fusion with a third input: live session vector.
- KAN decoder remains unchanged.
- Recompute risk at PDP view → add-to-cart → checkout.

Additional infrastructure:
- Client-side JS event capture.
- Redis-class low-latency session state.
- New-visitor cold-start path: product embedding + session vector + baseline model.

Early real-time accuracy is unvalidated and must be A/B tested.
