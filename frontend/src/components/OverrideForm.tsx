import { useState } from "react";
import { useApp } from "../context/AppContext";
import { useOverrideOrder } from "../api/hooks";

export default function OverrideForm({ orderId, currentScore }: { orderId: string; currentScore: number }) {
  const { actorName } = useApp();
  const [newScore, setNewScore] = useState(currentScore);
  const [reason, setReason] = useState("");
  const mutation = useOverrideOrder(orderId);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!reason.trim()) return;
    mutation.mutate(
      { new_score: newScore, reason, actor_name: actorName || undefined },
      { onSuccess: () => setReason("") },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded border border-neutral-200 p-3 dark:border-neutral-800">
      <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Override score</h3>
      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">
          New score: <span className="tabular-nums">{newScore.toFixed(2)}</span>
        </label>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={newScore}
          onChange={(e) => setNewScore(Number(e.target.value))}
          className="mt-1 w-full"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Reason (required)</label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          required
          rows={2}
          className="mt-1 w-full rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          placeholder="Why are you overriding the model's score?"
        />
      </div>
      <button
        type="submit"
        disabled={mutation.isPending || !reason.trim()}
        className="rounded bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
      >
        {mutation.isPending ? "Saving…" : "Apply override"}
      </button>
      {mutation.isError && <p className="text-xs text-red-600 dark:text-red-400">{(mutation.error as Error).message}</p>}
    </form>
  );
}
