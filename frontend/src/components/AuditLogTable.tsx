import { useState } from "react";
import { useAuditLog } from "../api/hooks";

export default function AuditLogTable() {
  const [eventType, setEventType] = useState("");
  const [actorRole, setActorRole] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, error } = useAuditLog({
    event_type: eventType || undefined,
    actor_role: actorRole || undefined,
    page,
    page_size: 25,
  });

  if (error) {
    return (
      <p className="text-sm text-red-600 dark:text-red-400">
        {(error as Error).message.includes("403")
          ? "Your current role can't view the audit log (requires Ops Manager or Admin)."
          : (error as Error).message}
      </p>
    );
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="space-y-3">
      <div className="flex gap-3">
        <select
          value={eventType}
          onChange={(e) => { setEventType(e.target.value); setPage(1); }}
          className="rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          <option value="">All event types</option>
          <option value="override">Overrides</option>
          <option value="intervention_action">Actions</option>
        </select>
        <select
          value={actorRole}
          onChange={(e) => { setActorRole(e.target.value); setPage(1); }}
          className="rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          <option value="">Any actor role</option>
          <option value="ops_analyst">Ops Analyst</option>
          <option value="ops_manager">Ops Manager</option>
          <option value="admin">Admin</option>
        </select>
      </div>

      {isLoading ? (
        <p className="text-sm text-neutral-500">Loading…</p>
      ) : (
        <>
          <table className="w-full border-collapse text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
              <tr>
                <th className="px-2 py-1 font-medium">When</th>
                <th className="px-2 py-1 font-medium">Order</th>
                <th className="px-2 py-1 font-medium">Tenant</th>
                <th className="px-2 py-1 font-medium">Event</th>
                <th className="px-2 py-1 font-medium">Actor</th>
                <th className="px-2 py-1 font-medium">Note</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items ?? []).map((e) => (
                <tr key={e.id} className="border-t border-neutral-100 dark:border-neutral-800">
                  <td className="px-2 py-1.5 text-xs text-neutral-500 dark:text-neutral-400">
                    {new Date(e.created_at).toLocaleString()}
                  </td>
                  <td className="px-2 py-1.5 font-mono text-xs">{e.order_id}</td>
                  <td className="px-2 py-1.5">{e.tenant}</td>
                  <td className="px-2 py-1.5">{e.event_type === "override" ? "Override" : e.action_type}</td>
                  <td className="px-2 py-1.5 text-xs">{e.actor_name || e.actor_role} ({e.actor_role})</td>
                  <td className="max-w-xs truncate px-2 py-1.5 text-xs text-neutral-500" title={e.note ?? undefined}>
                    {e.note}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between text-sm">
            <span className="text-neutral-500 dark:text-neutral-400">
              {data?.total ?? 0} entries — page {page} of {totalPages}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded border border-neutral-300 px-2 py-1 disabled:opacity-40 dark:border-neutral-700"
              >
                Previous
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded border border-neutral-300 px-2 py-1 disabled:opacity-40 dark:border-neutral-700"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
