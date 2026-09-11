import { Link } from "react-router-dom";
import type { AlertOut } from "../api/types";

function queueLink(alert: AlertOut): string {
  if (alert.cohort_type === "country") return `/queue?country=${encodeURIComponent(alert.cohort_key)}`;
  if (alert.cohort_type === "product_type") return `/queue?product_type=${encodeURIComponent(alert.cohort_key)}`;
  return "/queue";
}

export default function AlertsTable({ alerts }: { alerts: AlertOut[] }) {
  if (alerts.length === 0) {
    return (
      <p className="text-sm text-neutral-500 dark:text-neutral-400">
        No spikes detected — all cohorts are within their historical baseline (or don't yet have enough
        recent orders to evaluate).
      </p>
    );
  }

  return (
    <div className="overflow-auto rounded border border-neutral-200 dark:border-neutral-800">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-neutral-50 text-left text-xs uppercase tracking-wide text-neutral-500 dark:bg-neutral-900 dark:text-neutral-400">
          <tr>
            <th className="px-3 py-2 font-medium">Severity</th>
            <th className="px-3 py-2 font-medium">Tenant</th>
            <th className="px-3 py-2 font-medium">Cohort</th>
            <th className="px-3 py-2 font-medium">Baseline</th>
            <th className="px-3 py-2 font-medium">Recent actual</th>
            <th className="px-3 py-2 font-medium">Gap</th>
            <th className="px-3 py-2 font-medium">n (recent)</th>
            <th className="px-3 py-2 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((a, i) => (
            <tr key={i} className="border-t border-neutral-100 dark:border-neutral-800">
              <td className="px-3 py-2">
                <span
                  className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                    a.severity === "high"
                      ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300"
                      : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                  }`}
                >
                  {a.severity}
                </span>
              </td>
              <td className="px-3 py-2">{a.tenant}</td>
              <td className="px-3 py-2 font-mono text-xs">{a.cohort_type}: {a.cohort_key}</td>
              <td className="px-3 py-2 tabular-nums">{(a.baseline_rate * 100).toFixed(1)}%</td>
              <td className="px-3 py-2 tabular-nums">{(a.actual_rate * 100).toFixed(1)}%</td>
              <td className="px-3 py-2 tabular-nums font-medium">+{(a.gap * 100).toFixed(1)}pp</td>
              <td className="px-3 py-2 tabular-nums">{a.n_orders}</td>
              <td className="px-3 py-2">
                <Link to={queueLink(a)} className="text-xs text-blue-600 hover:underline dark:text-blue-400">
                  View queue →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
