import {
  Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { ReportingBucket } from "../api/types";

export default function BaselineActualChart({ buckets }: { buckets: ReportingBucket[] }) {
  if (buckets.length === 0) {
    return <p className="text-sm text-neutral-500 dark:text-neutral-400">No data for this selection.</p>;
  }

  const data = buckets.map((b) => ({
    bucket: b.bucket,
    "Actual outcome rate": Number((b.actual_return_rate * 100).toFixed(1)),
    "Historical baseline": Number((b.baseline_return_rate * 100).toFixed(1)),
    n: b.n_orders,
  }));

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-neutral-200 dark:stroke-neutral-800" />
          <XAxis dataKey="bucket" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} unit="%" width={48} />
          <Tooltip
            formatter={(value, name) => [`${value}%`, String(name)]}
            labelFormatter={(label, payload) => {
              const n = payload?.[0]?.payload?.n;
              return n !== undefined ? `${label} (n=${n})` : label;
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="Actual outcome rate" fill="#3b82f6" radius={[3, 3, 0, 0]} />
          <Line type="monotone" dataKey="Historical baseline" stroke="#f59e0b" strokeWidth={2} dot={false} strokeDasharray="6 4" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
