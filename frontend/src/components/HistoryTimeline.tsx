import { useState } from "react";
import { useUpdateActionOutcome } from "../api/hooks";
import { OUTCOMES, type HistoryEntry, type Outcome } from "../api/types";

const OUTCOME_LABELS: Record<Outcome, string> = {
  pending: "Pending",
  resolved_kept: "Resolved — order kept",
  resolved_prevented: "Resolved — RTO prevented",
  no_response: "No response",
};

function OutcomeEditor({ orderId, logId }: { orderId: string; logId: number }) {
  const [outcome, setOutcome] = useState<Outcome>("resolved_kept");
  const mutation = useUpdateActionOutcome(orderId);

  return (
    <div className="mt-1 flex items-center gap-2">
      <select
        value={outcome}
        onChange={(e) => setOutcome(e.target.value as Outcome)}
        className="rounded border border-neutral-300 bg-white px-1.5 py-0.5 text-xs dark:border-neutral-700 dark:bg-neutral-900"
      >
        {OUTCOMES.filter((o) => o !== "pending").map((o) => (
          <option key={o} value={o}>{OUTCOME_LABELS[o]}</option>
        ))}
      </select>
      <button
        type="button"
        onClick={() => mutation.mutate({ logId, body: { outcome } })}
        disabled={mutation.isPending}
        className="rounded border border-neutral-300 px-2 py-0.5 text-xs hover:bg-neutral-100 disabled:opacity-40 dark:border-neutral-700 dark:hover:bg-neutral-800"
      >
        Record outcome
      </button>
    </div>
  );
}

export default function HistoryTimeline({ orderId, entries }: { orderId: string; entries: HistoryEntry[] }) {
  if (entries.length === 0) {
    return <p className="text-sm text-neutral-500 dark:text-neutral-400">No actions or overrides logged yet.</p>;
  }

  return (
    <ol className="space-y-3">
      {entries.map((e) => (
        <li key={e.id} className="rounded border border-neutral-200 p-2.5 text-sm dark:border-neutral-800">
          <div className="flex items-center justify-between">
            <span className="font-medium text-neutral-900 dark:text-neutral-100">
              {e.event_type === "override" ? "Score override" : (e.action_type ?? "Action")}
            </span>
            <span className="text-xs text-neutral-500 dark:text-neutral-400">
              {new Date(e.created_at).toLocaleString()}
            </span>
          </div>
          <p className="text-xs text-neutral-500 dark:text-neutral-400">
            by {e.actor_name || e.actor_role} ({e.actor_role}) · {e.trigger === "automated_threshold" ? "automated" : "manual"}
          </p>
          {e.event_type === "override" && e.old_score !== null && e.new_score !== null && (
            <p className="mt-1 text-xs text-neutral-600 dark:text-neutral-300">
              {e.old_score.toFixed(2)} → {e.new_score.toFixed(2)}
            </p>
          )}
          {e.note && <p className="mt-1 text-neutral-700 dark:text-neutral-300">{e.note}</p>}
          {e.event_type === "intervention_action" && (
            <div className="mt-1">
              <span className="text-xs text-neutral-500 dark:text-neutral-400">
                Outcome: {e.outcome ? OUTCOME_LABELS[e.outcome] : "—"}
              </span>
              {e.outcome === "pending" && <OutcomeEditor orderId={orderId} logId={e.id} />}
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}
