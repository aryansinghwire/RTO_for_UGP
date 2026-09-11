import { useState } from "react";
import { useAlerts } from "../api/hooks";
import AlertsTable from "../components/AlertsTable";

export default function AlertsPage() {
  const [minGap, setMinGap] = useState(0.15);
  const { data, isLoading, error } = useAlerts({ min_gap: minGap });

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">Spike alerts</h2>
        <div className="flex items-center gap-2 text-sm">
          <label className="text-neutral-500 dark:text-neutral-400">Min gap:</label>
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={minGap}
            onChange={(e) => setMinGap(Number(e.target.value))}
            className="w-20 rounded border border-neutral-300 bg-white px-2 py-1 dark:border-neutral-700 dark:bg-neutral-900"
          />
        </div>
      </div>
      <p className="max-w-2xl text-xs text-neutral-500 dark:text-neutral-400">
        Compares each cohort's return/RTO rate over the last 14 days of (synthetic) order dates
        against its historical baseline. Cohorts with fewer than the minimum sample size are
        skipped to avoid noise from small groups.
      </p>
      {isLoading ? (
        <p className="text-sm text-neutral-500">Loading…</p>
      ) : error ? (
        <p className="text-sm text-red-600 dark:text-red-400">{(error as Error).message}</p>
      ) : (
        <AlertsTable alerts={data ?? []} />
      )}
    </div>
  );
}
