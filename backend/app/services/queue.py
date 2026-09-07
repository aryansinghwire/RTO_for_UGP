"""backend/app/services/queue.py - turns Order/OrderStatus ORM rows into the
API's list/detail shapes."""

import json

from ..models import Order, OrderStatus


def order_list_item(order: Order, status: OrderStatus) -> dict:
    return {
        "order_id": order.order_id,
        "tenant": order.tenant.name,
        "order_date": order.order_date,
        "customer_ref": order.customer_ref,
        "product_ref": order.product_ref,
        "current_score": status.current_score,
        "model_risk_score": order.model_risk_score,
        "status": status.status,
        "reasons": json.loads(order.reasons_json),
        "customer_no_history": bool(order.customer_no_history),
        "product_no_history": bool(order.product_no_history),
        "country_bucket": order.country_bucket,
        "product_brand_bucket": order.product_brand_bucket,
        "product_type_bucket": order.product_type_bucket,
    }


def order_detail(order: Order, status: OrderStatus) -> dict:
    base = order_list_item(order, status)
    base.update({
        "customer_return_rate": order.customer_return_rate,
        "product_return_rate": order.product_return_rate,
        "avg_discount_value": order.avg_discount_value,
        "avg_gbp_price": order.avg_gbp_price,
        "override_score": status.override_score,
        "override_reason": status.override_reason,
        "overridden_by": status.overridden_by,
        "overridden_at": status.overridden_at,
        "raw_features": json.loads(order.raw_features_json),
    })
    return base
