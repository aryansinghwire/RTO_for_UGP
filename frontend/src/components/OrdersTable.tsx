import { Link } from "react-router-dom";
import type { PaginatedOrders } from "../api/types";
import ScoreBadge from "./ScoreBadge";
import ColdStartBadge from "./ColdStartBadge";

const STATUS_CLASSES: Record<string, string> = {
  pending: "text-neutral-600 dark:text-neutral-400",
  overridden: "text-sky-600 dark:text-sky-400",
  actioned: "text-amber-600 dark:text-amber-400",
  closed: "text-emerald-600 dark:text-emerald-400",
};

interface Props {
  data: PaginatedOrders | undefined;
  isLoading: boolean;
  onPageChange: (page: number) => void;
}

export default function OrdersTable({ data, isLoading, onPageChange }: Props) {
  if (isLoading && !data) {
    return <p className="p-4 text-sm text-neutral-500">Loading orders…</p>;
  }
  if (!data || data.items.length === 0) {
    return <p className="p-4 text-sm text-neutral-500">No orders match these filters.</p>;
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 bg-neutral-50 text-left text-xs uppercase tracking-wide text-neutral-500 dark:bg-neutral-900 dark:text-neutral-400">
            <tr>
              <th className="px-3 py-2 font-medium">Order</th>
              <th className="px-3 py-2 font-medium">Tenant</th>
              <th className="px-3 py-2 font-medium">Date</th>
              <th className="px-3 py-2 font-medium">Score</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Flags</th>
              <th className="px-3 py-2 font-medium">Top reason</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((o) => (
              <tr
                key={o.order_id}
                className="border-b border-neutral-100 hover:bg-neutral-50 dark:border-neutral-800 dark:hover:bg-neutral-900"
              >
                <td className="px-3 py-2">
                  <Link to={`/orders/${o.order_id}`} className="font-mono text-xs text-blue-600 hover:underline dark:text-blue-400">
                    {o.order_id}
                  </Link>
                </td>
                <td className="px-3 py-2 text-neutral-700 dark:text-neutral-300">{o.tenant}</td>
                <td className="px-3 py-2 text-neutral-500 dark:text-neutral-400">{o.order_date}</td>
                <td className="px-3 py-2">
                  <ScoreBadge score={o.current_score} size="sm" />
                </td>
                <td className={`px-3 py-2 font-medium ${STATUS_CLASSES[o.status] ?? ""}`}>{o.status}</td>
                <td className="px-3 py-2">
                  <ColdStartBadge customerNoHistory={o.customer_no_history} productNoHistory={o.product_no_history} />
                </td>
                <td className="max-w-xs truncate px-3 py-2 text-neutral-500 dark:text-neutral-400" title={o.reasons[0]}>
                  {o.reasons[0]}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between border-t border-neutral-200 px-3 py-2 text-sm dark:border-neutral-800">
        <span className="text-neutral-500 dark:text-neutral-400">
          {data.total.toLocaleString()} orders — page {data.page} of {totalPages}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={data.page <= 1}
            onClick={() => onPageChange(data.page - 1)}
            className="rounded border border-neutral-300 px-2 py-1 disabled:opacity-40 dark:border-neutral-700"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={data.page >= totalPages}
            onClick={() => onPageChange(data.page + 1)}
            className="rounded border border-neutral-300 px-2 py-1 disabled:opacity-40 dark:border-neutral-700"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
