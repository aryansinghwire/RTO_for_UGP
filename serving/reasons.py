"""
serving/reasons.py - rule-based, human-readable "contributing reasons" for a
risk score. Deliberately NOT SHAP/feature-importance - just simple, named
thresholds on real columns, which is what the PRD asks for ("human-readable
contributing reasons" per order).

Hard rule: never reference the 13 lettered return-reason-code columns
(cust__customerId_level_return_code_*, prod__variantID_level_return_code_*) -
their letters have no known real-world meaning and must not be dressed up as
one.
"""

from config import HIGH_RETURN_RATE_THRESHOLD, HIGH_RISK_SCORE_THRESHOLD


def derive_reasons(row, risk_score, discount_p75_train):
    reasons = []
    product_cold = bool(row.get("product_no_history"))
    customer_cold = bool(row.get("customer_no_history"))

    if customer_cold:
        reasons.append(
            "New customer - no purchase history on file (cold-start fallback path)"
        )
    if product_cold:
        reasons.append(
            "New or rarely-seen product - limited historical data available"
        )

    # Return-rate/discount columns are MEAN-IMPUTED placeholders (not real
    # observed values) for no-history rows (see build_features.py's
    # role-aware imputation). Evaluating percentile/threshold rules against an
    # imputed placeholder would flag it as a genuine risk signal when it's
    # really just "we have no data" - so these checks only fire on rows with
    # real history for the relevant side.
    cust_rr = row.get("cust__customerReturnRate")
    if not customer_cold and cust_rr is not None and cust_rr >= HIGH_RETURN_RATE_THRESHOLD:
        reasons.append(
            f"Customer's historical return rate is high "
            f"({cust_rr:.0%}, threshold {HIGH_RETURN_RATE_THRESHOLD:.0%})"
        )

    prod_rr = row.get("prod__productReturnRate")
    if not product_cold and prod_rr is not None and prod_rr >= HIGH_RETURN_RATE_THRESHOLD:
        reasons.append(
            f"Product's historical return rate is high "
            f"({prod_rr:.0%}, threshold {HIGH_RETURN_RATE_THRESHOLD:.0%})"
        )

    discount = row.get("prod__avgDiscountValue")
    if (not product_cold and discount is not None and discount_p75_train is not None
            and discount >= discount_p75_train):
        reasons.append(
            "Order involves a deep discount (top quartile of discount depth, "
            "computed from training data)"
        )

    if not reasons:
        if risk_score >= HIGH_RISK_SCORE_THRESHOLD:
            reasons.append("Overall model-predicted risk is high")
        else:
            reasons.append("No significant individual risk factors identified for this order")

    return reasons
