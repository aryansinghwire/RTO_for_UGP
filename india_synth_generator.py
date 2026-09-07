#!/usr/bin/env python3
"""
india_synth_generator.py  —  Phase 8, Step 2 (PRD Section 8.2)
================================================================
Synthetic RTO/COD data generator for the Pre-Dispatch Return & RTO Risk Engine.

Produces the SAME six-file layout the ASOS pipeline already consumes
(event / customer / product  x  train / test), but with India D2C semantics
(RTO label, COD, pincode/zone tier, courier, discount depth, etc.).

KEY DESIGN PROPERTY (the one that matters, per handoff + PRD 8.2):
    isRTO is NOT an independent random column. It is a Bernoulli draw whose
    probability is a logistic function of COD flag, delivery-zone tier, the
    customer's latent RTO-proneness, discount depth, product proneness, courier,
    first-order flag and AOV band. Node-level rate features (customerRTORate,
    productRTORate, reason-code profiles) are then DERIVED from each entity's
    *train-period* events only -> they are historical, leakage-safe, noisy
    proxies of the latent proneness, exactly like customerReturnRate was in the
    real ASOS data (single-feature AUC 0.80, not 1.0).

Everything is seeded and CONFIG-driven. Nothing here needs pyg / torch — it is
pure numpy/pandas, so it runs anywhere (including an 8GB M2 Air) in seconds at
10K scale.

Usage:
    python india_synth_generator.py --scale small   --out data/synth
    python india_synth_generator.py --scale large   --out data/synth
    python india_synth_generator.py --orders 25000 --seed 7 --out data/synth
"""

import argparse, os, json, hashlib
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------- #
# CONFIG — target population parameters (PRD 8.2 benchmarks) + causal strengths
# ----------------------------------------------------------------------------- #
CONFIG = {
    # ---- population targets (calibrated to hit these) ----
    "overall_rto_rate":   0.30,    # PRD: ~30% overall RTO
    "cod_share":          0.63,    # PRD: ~63% COD
    "avg_rto_cost_inr":   300.0,   # PRD: ~Rs 300 per RTO event (carried as metadata)
    # conditional RTO anchors (ClickPost playbook: COD ~37.5% vs prepaid ~5.3%)
    "rto_rate_cod":       0.44,
    "rto_rate_prepaid":   0.075,

    # ---- scale presets (approx #orders/events) ----
    "scale_presets": {"small": 10_000, "large": 500_000},

    # ---- graph shape knobs ----
    # repeat-purchase: higher -> denser graph (more edges/customer). ASOS was
    # ~1.1 edges/node and that sparsity is WHY Node2Vec/fusion failed. Raise this
    # to test the parked "denser-subgraph" hypothesis (handoff Section 9).
    "orders_per_customer_mean": 1.8,
    "products_per_100_orders":  8,     # -> catalog size scales with volume
    "cold_start_test_frac":     0.70,  # target: frac of TEST customers unseen in TRAIN
    "test_period_frac":         0.35,  # last 35% of the time window = test

    # ---- delivery-zone tier mix (ClickPost: tier2+tier3 ~47% of volume) ----
    "zone_mix":   {"metro": 0.53, "tier2": 0.27, "tier3": 0.20},

    # ---- positive-control knob: inject PURELY RELATIONAL signal into the label
    # A two-hop co-purchase term (a customer's risk depends on the latent risk of
    # OTHER customers who buy the same products). Recoverable by GraphSAGE message
    # passing but NOT by any per-order/per-node feature a tabular model sees. Set
    # >0 only to test whether the GNN pipeline CAN detect graph signal when it
    # exists (positive control). Default 0.0 = honest, per-order-only data. Pair
    # with a higher orders_per_customer_mean so the co-purchase graph is dense
    # enough to carry the signal. ----
    "graph_signal_strength": 0.0,

    # ---- causal coefficients on the RTO logit (log-odds) ----
    # signs/relative magnitudes are the design; absolute level is auto-calibrated
    "beta": {
        "tier2":            0.45,   # tier2 modestly higher RTO
        "tier3":            0.95,   # tier3 clearly higher (ClickPost 2.2x metro)
        "cust_proneness":   1.95,   # latent per-customer RTO-proneness (z-scored).
                                    # Deliberately strong & UNOBSERVED for cold
                                    # customers -> makes cold-start the hard slice
                                    # (as in ASOS), and gives the graph model a
                                    # real per-customer signal to earn on.
        "prod_proneness":   0.80,   # latent per-product proneness (z-scored)
        "discount_depth":   0.60,   # deep discounts -> COD-abuse signal
        "first_order":      0.55,   # first-time buyers RTO more (29% vs 22%)
        "aov_ushape":       0.35,   # cheap & pricey orders RTO more (U-shape)
        "courier":          1.00,   # multiplies each courier's latent offset
    },

    # ---- couriers (each carries a latent RTO offset in log-odds; ClickPost:
    #      carrier x pincode is the single biggest tier2/3 lever). Offsets widened
    #      so the best-vs-worst courier gap in tier2/3 lands in the real ~20-25pp
    #      band (was ~8.6pp before - see realism audit). The tier-amplified courier
    #      term below makes the spread concentrate in tier2/3, as in real data. ----
    "couriers": {
        "Delhivery":  -0.35, "BlueDart": -0.70, "Ecom":    0.25,
        "XpressBees":  0.10, "Shadowfax": 0.55, "IndiaPost": 0.85,
    },
    "courier_tier_amplify": 1.35,  # courier offset x this in tier2/3 (concentrates
                                   # the carrier gap where ClickPost says it lives)

    # ---- product categories (apparel default, PRD 15.2) — 11 codes A..K ----
    "product_types": list("ABCDEFGHIJK"),
    # brands: exact ASOS set (A..K minus H) so Brand_* one-hots match your data
    "brands": list("ABCDEFGIJK"),
    "order_channels": ["app", "web", "marketplace"],
    # tier -> which Country_* slot it occupies (reuses ASOS geography one-hots)
    "tier_to_country": {"metro": "Country_A", "tier2": "Country_B", "tier3": "Country_C"},
    "country_slots": [f"Country_{c}" for c in "ABCDEFGHI"],
    "age_base_year": 2021,   # age = age_base_year - yearOfBirth (paper's convention)

    # ---- RTO-reason taxonomy (standard across brands, PRD 15.2). 13 codes A..M
    #      to mirror the ASOS 13-family structure the pipeline already handles ----
    "reason_codes": {
        "A": "cod_refusal", "B": "customer_unreachable", "C": "address_serviceability",
        "D": "changed_mind_doorstep", "E": "delayed_delivery", "F": "damaged_expectation",
        "G": "duplicate_order", "H": "payment_failure_doorstep", "I": "fake_malicious_order",
        "J": "out_of_delivery_area", "K": "repeated_attempt_failure", "L": "size_fit_doubt",
        "M": "other",
    },
}

# ----------------------------------------------------------------------------- #
# helpers
# ----------------------------------------------------------------------------- #
def _hash_id(prefix, i):
    return prefix + hashlib.sha1(f"{prefix}{i}".encode()).hexdigest()[:16]

def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))

def _zscore(a):
    a = np.asarray(a, dtype=float)
    s = a.std()
    return (a - a.mean()) / (s if s > 1e-9 else 1.0)


# ----------------------------------------------------------------------------- #
# 1. Entities
# ----------------------------------------------------------------------------- #
def make_customers(n, rng, cfg):
    zones = list(cfg["zone_mix"].keys())
    zprob = np.array(list(cfg["zone_mix"].values()))
    tier  = rng.choice(zones, size=n, p=zprob)

    # repeat-customer segment: ~35% are repeat buyers (lower proneness, more orders)
    is_repeat = rng.random(n) < 0.35
    # latent RTO-proneness: repeat buyers lower, tier3 higher, plus noise
    base = rng.normal(0, 1, n)
    base += np.where(is_repeat, -0.55, 0.0)
    base += np.where(tier == "tier3", 0.35, 0.0)
    base += np.where(tier == "tier2", 0.12, 0.0)
    proneness = _zscore(base)

    year = rng.integers(1965, 2005, n)               # yearOfBirth
    is_male = (rng.random(n) < 0.55).astype(int)
    premier = ((rng.random(n) < 0.18) | (is_repeat & (rng.random(n) < 0.4))).astype(int)
    pincode = rng.integers(110001, 855126, n)         # india pincode range

    return pd.DataFrame({
        "customerId":      [_hash_id("C", i) for i in range(n)],
        "_proneness":      proneness,      # latent (private, dropped before save)
        "_is_repeat":      is_repeat,
        "deliveryZoneTier": tier,
        "pincode":         pincode,
        "yearOfBirth":     year,
        "isMale":          is_male,
        "premier":         premier,
    })


def make_products(n, rng, cfg):
    ptype = rng.choice(cfg["product_types"], size=n)
    brand = rng.choice(cfg["brands"], size=n)
    # price: log-normal, INR; discount depth 0..0.6, mildly higher on cheaper items
    price = np.round(rng.lognormal(mean=6.6, sigma=0.55, size=n), 0)   # ~e^6.6≈735 median
    price = np.clip(price, 199, 15000)
    discount = np.clip(rng.beta(2.2, 5.0, n) * 0.6 + rng.normal(0, 0.02, n), 0.0, 0.6)
    prod_prone = _zscore(rng.normal(0, 1, n) + 0.25 * _zscore(discount))

    return pd.DataFrame({
        "variantId":   [_hash_id("V", i) for i in range(n)],
        "productId":   [_hash_id("P", i) for i in range(n // 3 + 1)][ :n] if False else
                       [_hash_id("P", i // 3) for i in range(n)],  # ~3 variants/product
        "supplierRef": [_hash_id("S", i // 12) for i in range(n)],  # ~12 variants/supplier
        "_prod_prone": prod_prone,
        "productType": ptype,
        "brand": brand,
        "avgInrPrice": price,
        "avgDiscountValue": np.round(discount, 3),
    })


# ----------------------------------------------------------------------------- #
# 2. Orders (events) with causal RTO label
# ----------------------------------------------------------------------------- #
def make_events(customers, products, n_orders, rng, cfg):
    nc, np_ = len(customers), len(products)
    train_end = 1 - cfg["test_period_frac"]

    # ---- ESTABLISHED customers: repeat buyers, orders across full timeline ----
    #      -> these build the (denser) training graph the model learns on.
    #      NEW customers: first-time buyers who arrive test-only -> genuine cold
    #      cases, mirroring both ASOS's cold-start dominance and India's first-
    #      time-buyer skew. Cold-start fraction is thus a direct knob.
    est_mask = customers["_is_repeat"].values | (rng.random(nc) < 0.25)
    est_idx  = np.where(est_mask)[0]
    new_idx  = np.where(~est_mask)[0]

    # established order counts (repeat-heavy Poisson) -> edges/customer knob
    lam = cfg["orders_per_customer_mean"] * np.where(
        customers["_is_repeat"].values[est_idx], 2.4, 1.0)
    ecounts = 1 + rng.poisson(np.clip(lam - 1, 0.05, None))
    est_orders = int(ecounts.sum())

    # size NEW cohort to hit the target cold-start fraction among test customers.
    # expected warm-in-test established custs W ~= est custs with >=1 test order.
    p_train = train_end
    W = np.sum(1 - p_train ** ecounts)               # E[#established w/ a test order]
    cf = cfg["cold_start_test_frac"]
    n_new = int(round(cf / (1 - cf) * W))
    n_new = min(n_new, len(new_idx)) if len(new_idx) else n_new
    if len(new_idx) < n_new:                          # pad pool of new custs if short
        new_idx = np.concatenate([new_idx, rng.choice(est_idx, n_new - len(new_idx), replace=False)])
    new_idx = new_idx[:n_new]

    # assemble order->customer index and per-order time
    cust_idx = np.concatenate([np.repeat(est_idx, ecounts), new_idx])
    est_times = rng.random(est_orders)                               # Uniform(0,1)
    new_times = train_end + rng.random(n_new) * (1 - train_end)      # test window only
    order_time = np.concatenate([est_times, new_times])

    # trim/scale toward requested n_orders (established side only; keep all new)
    m = len(cust_idx)
    if m > n_orders * 1.15:
        keep_est = np.argsort(rng.random(est_orders))[: max(n_orders - n_new, 1)]
        keep = np.concatenate([keep_est, np.arange(est_orders, m)])
        cust_idx, order_time = cust_idx[keep], order_time[keep]
        m = len(cust_idx)

    perm = rng.permutation(m)
    cust_idx, order_time = cust_idx[perm], order_time[perm]

    # product choice: mild popularity skew (some products sell far more)
    pop = rng.dirichlet(np.ones(np_) * 0.6)
    prod_idx = rng.choice(np.arange(np_), size=m, p=pop)

    c = customers.iloc[cust_idx].reset_index(drop=True)
    p = products.iloc[prod_idx].reset_index(drop=True)

    # ---- temporal train/test split ----
    is_test = order_time >= train_end

    # ---- payment method: 63% COD overall, more COD in tier3 & first orders ----
    tier = c["deliveryZoneTier"].values
    cod_logit = (np.log(cfg["cod_share"]/(1-cfg["cod_share"]))
                 + 0.35*(tier == "tier3") + 0.15*(tier == "tier2")
                 - 0.20*(c["premier"].values == 1))
    is_cod = rng.random(m) < _sigmoid(cod_logit)

    # first-order flag (per customer, by time order)
    order_rank = (pd.Series(order_time).groupby(cust_idx).rank(method="first").values)
    is_first = (order_rank == 1)

    # discount depth (from product), AOV band, courier
    disc = p["avgDiscountValue"].values
    price = p["avgInrPrice"].values
    aov_z = _zscore(np.log(price))
    aov_ushape = aov_z**2 - 1.0                       # U-shape: high at both tails
    courier_names = list(cfg["couriers"].keys())
    courier = rng.choice(courier_names, size=m)
    courier_off = np.array([cfg["couriers"][k] for k in courier])
    # concentrate the carrier gap in tier2/3 (where ClickPost says it lives)
    amp = np.where(np.isin(tier, ["tier2", "tier3"]), cfg.get("courier_tier_amplify", 1.0), 1.0)
    courier_off = courier_off * amp

    # ---- OPTIONAL relational signal (positive control) --------------------
    # Two-hop co-purchase risk: hop1 = mean latent proneness of customers on each
    # product; hop2 = mean of that over the products each customer buys. This is a
    # graph aggregation invisible to per-order features - only message passing can
    # recover it. Zero-cost when the knob is 0.
    gs = cfg.get("graph_signal_strength", 0.0)
    if gs > 0:
        prone_ord = customers["_proneness"].values[cust_idx]
        rel = pd.DataFrame({"c": cust_idx, "p": prod_idx, "prone": prone_ord})
        # LEAVE-ONE-OUT product-level mean: a naive groupby(...).transform("mean")
        # includes each row's OWN proneness in its product's average - with modest
        # orders-per-product, self-contribution dominates and the "relational" term
        # ends up correlated ~0.55 with the customer's OWN proneness, i.e. it leaks
        # straight back into something customerReturnRate already exposes to a
        # tabular model. Leave-one-out removes that: (group_sum - self) / (n - 1).
        grp = rel.groupby("p")["prone"]
        grp_sum = grp.transform("sum")
        grp_n = grp.transform("count")
        prod_risk = np.where(grp_n > 1, (grp_sum - rel["prone"]) / (grp_n - 1),
                             rel["prone"].mean())   # singleton products: population mean
        rel["prod_risk"] = prod_risk
        cust_rel = rel.groupby("c")["prod_risk"].transform("mean").values
        rel_term = gs * _zscore(cust_rel)
    else:
        rel_term = 0.0

    # ---- RTO logit (the causal core) ----
    b = cfg["beta"]
    logit = (
        b["tier2"]*(tier == "tier2") + b["tier3"]*(tier == "tier3")
        + b["cust_proneness"]*c["_proneness"].values
        + b["prod_proneness"]*p["_prod_prone"].values
        + b["discount_depth"]*_zscore(disc)
        + b["first_order"]*is_first
        + b["aov_ushape"]*aov_ushape
        + b["courier"]*courier_off
        + rel_term
    )
    # calibrate a COD gap + global intercept to hit the two conditional anchors
    logit, cod_bump, intercept = _calibrate(logit, is_cod, rng, cfg)

    p_rto = _sigmoid(logit)
    is_rto = (rng.random(m) < p_rto).astype(int)

    # ---- reason codes for RTO events (cause-dependent) ----
    reasons = _draw_reasons(is_rto, is_cod, tier, is_first, rng, cfg)

    events = pd.DataFrame({
        "variantId":  p["variantId"].values,
        "customerId": c["customerId"].values,
        "isReturned": is_rto,          # ASOS label name; value = RTO (pre-delivery)
        "paymentMethod": np.where(is_cod, "COD", "prepaid"),
        "deliveryZoneTier": tier,
        "courierPartner": courier,
        "orderChannel": rng.choice(cfg["order_channels"], size=m, p=[0.55, 0.35, 0.10]),
        "promoCode":   (disc > 0.25).astype(int),       # deep-discount proxy for promo
        "deliveryAttemptCount": 1 + (is_rto * rng.integers(0, 3, m)),
        "_order_time": order_time,
        "_is_test":    is_test,
        "_reason":     reasons,
        "_cust_idx":   cust_idx,
        "_prod_idx":   prod_idx,
    })
    # promised delivery date: pseudo-date from order_time + tier-dependent SLA
    sla = np.where(tier == "metro", 2, np.where(tier == "tier2", 4, 6))
    base_day = (order_time * 120).astype(int)
    events["promisedDeliveryDate"] = pd.to_datetime("2025-01-01") + pd.to_timedelta(base_day + sla, unit="D")

    diag = {"cod_bump": float(cod_bump), "intercept": float(intercept)}
    return events, diag


def _calibrate(base_logit, is_cod, rng, cfg, iters=60):
    """Solve (intercept, cod_bump) so realized RTO matches prepaid & COD anchors."""
    target_cod = np.log(cfg["rto_rate_cod"]/(1-cfg["rto_rate_cod"]))
    target_pp  = np.log(cfg["rto_rate_prepaid"]/(1-cfg["rto_rate_prepaid"]))
    intercept, cod_bump = 0.0, 0.0
    for _ in range(iters):
        logit = base_logit + intercept + cod_bump*is_cod
        p = _sigmoid(logit)
        pp_rate  = p[~is_cod].mean()
        cod_rate = p[is_cod].mean()
        # nudge intercept toward prepaid anchor, cod_bump toward COD gap
        intercept += 0.9*(target_pp - np.log(pp_rate/(1-pp_rate)))
        cur_gap = np.log(cod_rate/(1-cod_rate)) - np.log(pp_rate/(1-pp_rate))
        cod_bump += 0.9*((target_cod - target_pp) - cur_gap)
    return base_logit + intercept + cod_bump*is_cod, cod_bump, intercept


def _draw_reasons(is_rto, is_cod, tier, is_first, rng, cfg):
    codes = list(cfg["reason_codes"].keys())          # A..M
    reasons = np.array(["" for _ in range(len(is_rto))], dtype=object)
    idx = np.where(is_rto == 1)[0]
    for i in idx:
        w = np.ones(len(codes)) * 0.4
        cd = {c: j for j, c in enumerate(codes)}
        if is_cod[i]:
            w[cd["A"]] += 3.0; w[cd["H"]] += 1.2; w[cd["I"]] += 0.8   # cod refusal / payment / fake
        else:
            w[cd["D"]] += 1.5; w[cd["L"]] += 1.2                       # changed mind / size doubt
        if tier[i] == "tier3":
            w[cd["C"]] += 1.5; w[cd["J"]] += 1.5; w[cd["B"]] += 1.0    # serviceability / area / unreachable
        if is_first[i]:
            w[cd["B"]] += 0.8; w[cd["A"]] += 0.6
        w[cd["E"]] += 0.6; w[cd["K"]] += 0.5
        reasons[i] = rng.choice(codes, p=w / w.sum())
    return reasons


# ----------------------------------------------------------------------------- #
# 3. Derive node tables from TRAIN-period events (leakage-safe historical rates)
# ----------------------------------------------------------------------------- #
def build_node_tables(events, customers, products, cfg):
    """Emit customer/product node tables using the EXACT ASOS column names, so the
    existing pipeline runs unchanged. India semantics ride inside those columns:
      - customerReturnRate now means the RTO rate (label = isReturned = RTO)
      - Country_A/B/C encode metro/tier-2/tier-3 (real pincode -> tier, in the
        Shopify step; synthetic tier for now)
      - avgGbpPrice holds the INR price value (name kept for pipeline compatibility)
    """
    codes = list(cfg["reason_codes"].keys())
    train = events[~events["_is_test"]]

    def agg_side(df_train, id_col, id_all, sales_name, ret_name, rate_name, rc_prefix):
        g = df_train.groupby(id_col)
        sales = g.size().rename(sales_name)
        rets  = g["isReturned"].sum().rename(ret_name)
        rate  = g["isReturned"].mean().rename(rate_name)
        rmask = df_train[df_train["isReturned"] == 1]
        rc = rmask.groupby([id_col, "_reason"]).size().unstack(fill_value=0)
        rc = rc.reindex(columns=codes, fill_value=0)
        rc = rc.div(rc.sum(axis=1).replace(0, np.nan), axis=0)
        rc.columns = [f"{rc_prefix}_level_return_code_{c}" for c in codes]
        node = pd.concat([sales, rets, rate, rc], axis=1).reindex(id_all)
        return node

    cust_agg = agg_side(train, "customerId", customers["customerId"],
                        "salesPerCustomer", "returnsPerCustomer",
                        "customerReturnRate", "customerId")
    prod_agg = agg_side(train, "variantId", products["variantId"],
                        "salesPerProduct", "returnsPerProduct",
                        "productReturnRate", "variantID")

    # ---------- CUSTOMER node table (exact ASOS 31-col schema) ----------
    cust = customers.set_index("customerId")
    # tier -> shippingCountry string + Country_* one-hots (reuse geography slots)
    ship = cust["deliveryZoneTier"].map(cfg["tier_to_country"])   # e.g. tier3 -> Country_C
    cust["shippingCountry"] = ship
    for slot in cfg["country_slots"]:
        cust[slot] = (ship == slot).astype(int)
    cust["age"] = cfg["age_base_year"] - cust["yearOfBirth"]
    cust = cust.join(cust_agg)
    cust = cust.reset_index().rename(columns={"customerId": "hash(customerId)"})
    cust_cols = (["hash(customerId)", "yearOfBirth", "isMale", "shippingCountry",
                  "premier", "salesPerCustomer", "returnsPerCustomer", "customerReturnRate"]
                 + [f"customerId_level_return_code_{c}" for c in codes]
                 + cfg["country_slots"] + ["age"])
    cust = cust[cust_cols]

    # ---------- PRODUCT node table (exact ASOS 42-col schema) ----------
    prod = products.set_index("variantId")
    prod = prod.rename(columns={"avgInrPrice": "avgGbpPrice"})   # keep name; value is INR
    for b in cfg["brands"]:
        prod[f"Brand_{b}"] = (prod["brand"] == b).astype(int)
    for t in cfg["product_types"]:
        prod[f"productType_{t}"] = (prod["productType"] == t).astype(int)
    prod = prod.join(prod_agg)
    prod = prod.reset_index().rename(columns={
        "variantId": "hash(variantID)", "productId": "hash(productID)",
        "supplierRef": "hash(supplierRef)"})
    prod_cols = (["hash(variantID)", "hash(productID)", "hash(supplierRef)",
                  "avgGbpPrice", "avgDiscountValue", "salesPerProduct",
                  "returnsPerProduct", "productReturnRate"]
                 + [f"variantID_level_return_code_{c}" for c in codes]
                 + [f"Brand_{b}" for b in cfg["brands"]]
                 + [f"productType_{t}" for t in cfg["product_types"]])
    prod = prod[prod_cols]

    return cust, prod


# ----------------------------------------------------------------------------- #
# 4. Split + save the six tables
# ----------------------------------------------------------------------------- #
def split_and_save(events, cust, prod, out_dir, cfg, seed):
    os.makedirs(out_dir, exist_ok=True)

    # MAIN event table = exact ASOS 3-column edge+label schema -> pipeline runs unchanged
    ev3 = ["variantId", "customerId", "isReturned"]
    rename3 = {"variantId": "hash(variantID)", "customerId": "hash(customerId)"}
    ev_train = events[~events["_is_test"]][ev3].rename(columns=rename3).reset_index(drop=True)
    ev_test  = events[ events["_is_test"]][ev3].rename(columns=rename3).reset_index(drop=True)

    # India-only order-level fields kept in a SIDE file (nothing lost). Promote these
    # to real event features in the Shopify step, where COD/courier are genuine columns.
    india_cols = ["variantId", "customerId", "isReturned", "paymentMethod",
                  "deliveryZoneTier", "courierPartner", "orderChannel", "promoCode",
                  "deliveryAttemptCount", "promisedDeliveryDate", "_is_test"]
    events[india_cols].rename(columns=rename3).to_pickle(
        os.path.join(out_dir, "event_india_extra.p"))

    # exact ASOS filenames -> literal drop-in replacement for data/clean/
    tables = {
        "event_table_training.p":   ev_train, "event_table_testing.p":    ev_test,
        "customer_nodes_training.p": cust,    "customer_nodes_testing.p":  cust,
        "product_nodes_training.p":  prod,    "product_nodes_testing.p":   prod,
    }
    for fname, df in tables.items():
        df.to_pickle(os.path.join(out_dir, fname))

    meta = {
        "seed": seed, "generator_version": "india_synth_v2_asos_schema",
        "avg_rto_cost_inr": cfg["avg_rto_cost_inr"],
        "reason_codes": cfg["reason_codes"],
        "note": "isReturned column = RTO label; Country_A/B/C = metro/tier2/tier3; "
                "avgGbpPrice value is INR; India order fields in event_india_extra.p",
        "n_event_train": len(ev_train), "n_event_test": len(ev_test),
        "n_customers": len(cust), "n_products": len(prod),
    }
    with open(os.path.join(out_dir, "synth_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    return tables


# ----------------------------------------------------------------------------- #
# main
# ----------------------------------------------------------------------------- #
def generate(n_orders, seed, out_dir, cfg=CONFIG, verbose=True):
    rng = np.random.default_rng(seed)
    n_cust = max(int(n_orders / cfg["orders_per_customer_mean"]), 10)
    n_prod = max(int(n_orders * cfg["products_per_100_orders"] / 100), 5)

    customers = make_customers(n_cust, rng, cfg)
    products  = make_products(n_prod, rng, cfg)
    events, diag = make_events(customers, products, n_orders, rng, cfg)
    cust, prod = build_node_tables(events, customers, products, cfg)
    tables = split_and_save(events, cust, prod, out_dir, cfg, seed)

    if verbose:
        _report(events, cust, prod, tables, diag, cfg)
    return events, cust, prod, tables


def _report(events, cust, prod, tables, diag, cfg):
    m = len(events)
    cod = events["paymentMethod"].eq("COD")
    print("=" * 68)
    print("SYNTHETIC INDIA RTO DATA — CALIBRATION REPORT")
    print("=" * 68)
    print(f"orders (events)      : {m:,}   train={len(tables['event_table_training.p']):,}  test={len(tables['event_table_testing.p']):,}")
    print(f"customers / products : {len(cust):,} / {len(prod):,}")
    print(f"overall RTO rate     : {events['isReturned'].mean():.3f}   (target {cfg['overall_rto_rate']})")
    print(f"COD share            : {cod.mean():.3f}   (target {cfg['cod_share']})")
    print(f"  RTO | COD          : {events.loc[cod,'isReturned'].mean():.3f}   (target {cfg['rto_rate_cod']})")
    print(f"  RTO | prepaid      : {events.loc[~cod,'isReturned'].mean():.3f}   (target {cfg['rto_rate_prepaid']})")
    for t in ["metro", "tier2", "tier3"]:
        mask = events["deliveryZoneTier"].eq(t)
        print(f"  RTO | {t:<6}       : {events.loc[mask,'isReturned'].mean():.3f}   ({mask.mean():.2f} of vol)")
    # graph density + cold start
    edges_per_cust = m / len(cust)
    train_ids = set(tables["event_table_training.p"]["hash(customerId)"])
    test_ids  = set(tables["event_table_testing.p"]["hash(customerId)"])
    cold = len(test_ids - train_ids) / max(len(test_ids), 1)
    print(f"edges / customer     : {edges_per_cust:.2f}   (ASOS was ~1.1)")
    print(f"cold-start test cust : {cold:.3f}   (target ~{cfg['cold_start_test_frac']})")
    print(f"calibration diag     : intercept={diag['intercept']:+.2f}  cod_bump={diag['cod_bump']:+.2f}")
    print("=" * 68)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", choices=["small", "large"], default="small")
    ap.add_argument("--orders", type=int, default=None, help="override #orders")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/synth")
    ap.add_argument("--graph-signal", type=float, default=None,
                    help="relational-signal strength for positive control (0=off, "
                         "try 1.5-2.5). Injects graph-only signal into the label.")
    ap.add_argument("--density", type=float, default=None,
                    help="override orders_per_customer_mean (graph density). Pair a "
                         "higher value, e.g. 6, with --graph-signal for the control.")
    args = ap.parse_args()
    if args.graph_signal is not None:
        CONFIG["graph_signal_strength"] = args.graph_signal
    if args.density is not None:
        CONFIG["orders_per_customer_mean"] = args.density
    n = args.orders or CONFIG["scale_presets"][args.scale]
    generate(n, args.seed, args.out)