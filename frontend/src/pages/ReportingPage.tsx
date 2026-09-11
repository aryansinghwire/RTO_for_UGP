import { useState } from "react";
import { useReporting } from "../api/hooks";
import type { CohortType, Granularity } from "../api/types";
import BaselineActualChart from "../components/BaselineActualChart";

const COUNTRY_BUCKETS = ["Country_A", "Country_B", "Country_C", "Country_D", "Country_E",
  "Country_F", "Country_G", "Country_H", "Country_I"];
const PRODUCT_TYPE_BUCKETS = ["productType_A", "productType_B", "productType_C", "productType_D",
  "productType_E", "productType_F", "productType_G", "productType_H", "productType_I",
  "productType_J", "productType_K"];

export default function ReportingPage() {
  const [cohortType, setCohortType] = useState<CohortType>("overall");
  const [cohortKey, setCohortKey] = useState("");
  const [granularity, setGranularity] = useState<Granularity>("week");

  const { data, isLoading, error } = useReporting({
    cohort_type: cohortType,
    cohort_key: cohortType === "overall" ? undefined : cohortKey || undefined,
    granularity,
  });

  const buckets = data?.buckets ?? [];
  const totalOrders = buckets.reduce((s, b) => s + b.n_orders, 0);
  const weightedActual = totalOrders
    ? buckets.reduce((s, b) => s + b.actual_return_rate * b.n_orders, 0) / totalOrders
    : 0;
  const baseline = buckets[0]?.baseline_return_rate ?? 0;

  return (
    <div className="space-y-6 p-4">
      <h2 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
        Baseline vs. actual (RTO/return rate)
      </h2>
      <p className="max-w-2xl text-xs text-neutral-500 dark:text-neutral-400">
        "Baseline" is each cohort's historical return-rate feature (computed upstream, before this
        replay). "Actual" is the observed outcome rate of these historical test orders, bucketed by
        their (synthetic) order date. This replays past orders as a live feed for demonstration —
        it is not a forecast of future orders.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Cohort</label>
          <select
            value={cohortType}
            onChange={(e) => { setCohortType(e.target.value as CohortType); setCohortKey(""); }}
            className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          >
            <option value="overall">Overall</option>
            <option value="country">Country bucket</option>
            <option value="product_type">Product type bucket</option>
            <option value="product">Specific product (ref)</option>
          </select>
        </div>

        {cohortType === "country" && (
          <div>
            <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Bucket</label>
            <select
              value={cohortKey}
              onChange={(e) => setCohortKey(e.target.value)}
              className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
            >
              <option value="">Select…</option>
              {COUNTRY_BUCKETS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        )}
        {cohortType === "product_type" && (
          <div>
            <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Bucket</label>
            <select
              value={cohortKey}
              onChange={(e) => setCohortKey(e.target.value)}
              className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
            >
              <option value="">Select…</option>
              {PRODUCT_TYPE_BUCKETS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        )}
        {cohortType === "product" && (
          <div>
            <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Product ref</label>
            <input
              value={cohortKey}
              onChange={(e) => setCohortKey(e.target.value)}
              placeholder="product_ref (see order detail)"
              className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
            />
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Granularity</label>
          <select
            value={granularity}
            onChange={(e) => setGranularity(e.target.value as Granularity)}
            className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          >
            <option value="week">Weekly</option>
            <option value="day">Daily</option>
          </select>
        </div>
      </div>

      {cohortType !== "overall" && !cohortKey ? (
        <p className="text-sm text-neutral-500 dark:text-neutral-400">Select a cohort value above.</p>
      ) : error ? (
        <p className="text-sm text-red-600 dark:text-red-400">{(error as Error).message}</p>
      ) : isLoading ? (
        <p className="text-sm text-neutral-500">Loading…</p>
      ) : (
        <>
          <div className="flex gap-6">
            <KpiTile label="Orders in range" value={totalOrders.toLocaleString()} />
            <KpiTile label="Weighted actual rate" value={`${(weightedActual * 100).toFixed(1)}%`} />
            <KpiTile label="Historical baseline" value={`${(baseline * 100).toFixed(1)}%`} />
          </div>
          <BaselineActualChart buckets={buckets} />
        </>
      )}
    </div>
  );
}

function KpiTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-neutral-200 px-4 py-2 dark:border-neutral-800">
      <p className="text-xs text-neutral-500 dark:text-neutral-400">{label}</p>
      <p className="text-xl font-semibold tabular-nums text-neutral-900 dark:text-neutral-100">{value}</p>
    </div>
  );
}
