"""
serving/synth.py - generates the display-only fields that don't exist in the
real dataset (order id, order date, tenant). Every function here is seeded and
deterministic, and every value it produces is designed to be obviously a demo
construct (see config.PROTOTYPE_NOTICE).
"""

import numpy as np
import pandas as pd

from config import DATE_WINDOW, ORDER_ID_PREFIX, TENANT_NAMES, TENANT_WEIGHTS


def make_order_ids(n):
    return [f"{ORDER_ID_PREFIX}{i + 1:06d}" for i in range(n)]


def make_order_dates(n, seed, window=DATE_WINDOW):
    """Uniform random dates across the dataset's real test window (Oct-Nov
    2021). There is no per-order timestamp anywhere in this dataset - this is
    purely so the dashboard has *something* to plot a timeline/trend against."""
    start = pd.Timestamp(window[0])
    end = pd.Timestamp(window[1])
    span_days = (end - start).days
    rng = np.random.RandomState(seed)
    offsets = rng.uniform(0, span_days, size=n)
    dates = [(start + pd.Timedelta(days=float(o))).strftime("%Y-%m-%d") for o in offsets]
    return dates


def assign_tenants(customer_ids, seed, names=TENANT_NAMES, weights=TENANT_WEIGHTS):
    """Assigns each row a tenant, keyed by CUSTOMER (not per-row), so a given
    customer's orders all land in the same demo tenant - mirroring how a real
    customer belongs to one brand's install, not a random one per order."""
    customer_ids = pd.Series(customer_ids).astype(str)
    unique_customers = customer_ids.unique()
    rng = np.random.RandomState(seed)
    tenant_per_customer = rng.choice(names, size=len(unique_customers), p=weights)
    mapping = dict(zip(unique_customers, tenant_per_customer))
    return customer_ids.map(mapping).to_numpy()
