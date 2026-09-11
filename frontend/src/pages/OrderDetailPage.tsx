import { Link, useParams } from "react-router-dom";
import { useOrder, useOrderHistory } from "../api/hooks";
import ScoreBadge from "../components/ScoreBadge";
import ColdStartBadge from "../components/ColdStartBadge";
import ReasonsList from "../components/ReasonsList";
import OverrideForm from "../components/OverrideForm";
import InterventionActionForm from "../components/InterventionActionForm";
import HistoryTimeline from "../components/HistoryTimeline";

export default function OrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { data: order, isLoading, error } = useOrder(orderId);
  const { data: history } = useOrderHistory(orderId);

  if (isLoading) return <p className="p-4 text-sm text-neutral-500">Loading order…</p>;
  if (error || !order) {
    return (
      <div className="p-4">
        <p className="text-sm text-red-600 dark:text-red-400">
          {(error as Error)?.message ?? "Order not found."}
        </p>
        <Link to="/queue" className="text-sm text-blue-600 hover:underline dark:text-blue-400">← Back to queue</Link>
      </div>
    );
  }

  const rawEntries = Object.entries(order.raw_features).filter(
    ([, v]) => typeof v !== "object" || v === null,
  );
  const profileEntries = Object.entries(order.raw_features).filter(
    ([, v]) => typeof v === "object" && v !== null,
  );

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4">
      <div>
        <Link to="/queue" className="text-sm text-blue-600 hover:underline dark:text-blue-400">← Back to queue</Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h2 className="font-mono text-lg font-semibold text-neutral-900 dark:text-neutral-100">{order.order_id}</h2>
          <ScoreBadge score={order.current_score} />
          <span className="text-sm text-neutral-500 dark:text-neutral-400">
            {order.tenant} · {order.order_date} · status: {order.status}
          </span>
        </div>
        {order.current_score !== order.model_risk_score && (
          <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
            Original model score: {order.model_risk_score.toFixed(2)} (overridden to {order.current_score.toFixed(2)}
            {order.override_reason ? ` — "${order.override_reason}"` : ""})
          </p>
        )}
        <div className="mt-2">
          <ColdStartBadge customerNoHistory={order.customer_no_history} productNoHistory={order.product_no_history} />
        </div>
      </div>

      <section>
        <h3 className="mb-1 text-sm font-semibold text-neutral-900 dark:text-neutral-100">Contributing reasons</h3>
        <ReasonsList reasons={order.reasons} />
      </section>

      <section className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
        <Field label="Customer return rate" value={`${(order.customer_return_rate * 100).toFixed(1)}%`} />
        <Field label="Product return rate" value={`${(order.product_return_rate * 100).toFixed(1)}%`} />
        <Field label="Avg discount value" value={order.avg_discount_value.toFixed(2)} />
        <Field label="Avg price" value={order.avg_gbp_price.toFixed(2)} />
        <Field label="Country bucket" value={order.country_bucket} />
        <Field label="Product brand bucket" value={order.product_brand_bucket} />
        <Field label="Product type bucket" value={order.product_type_bucket} />
        <Field label="Customer ref" value={order.customer_ref} mono />
        <Field label="Product ref" value={order.product_ref} mono />
      </section>

      {rawEntries.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer font-semibold text-neutral-900 dark:text-neutral-100">
            Additional feature drill-down
          </summary>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {rawEntries.map(([k, v]) => (
              <Field key={k} label={k} value={String(v)} />
            ))}
          </div>
          {profileEntries.map(([k, v]) => (
            <div key={k} className="mt-2">
              <p className="text-xs font-medium text-neutral-500 dark:text-neutral-400">{k}</p>
              <p className="font-mono text-xs text-neutral-600 dark:text-neutral-300">{JSON.stringify(v)}</p>
            </div>
          ))}
        </details>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <OverrideForm orderId={order.order_id} currentScore={order.current_score} />
        <InterventionActionForm orderId={order.order_id} />
      </div>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-neutral-900 dark:text-neutral-100">History</h3>
        <HistoryTimeline orderId={order.order_id} entries={history ?? []} />
      </section>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs text-neutral-500 dark:text-neutral-400">{label}</p>
      <p className={mono ? "font-mono text-xs text-neutral-800 dark:text-neutral-200" : "text-neutral-800 dark:text-neutral-200"}>
        {value}
      </p>
    </div>
  );
}
