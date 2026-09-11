import { useState } from "react";
import { useApp } from "../context/AppContext";
import { useCreateAction } from "../api/hooks";
import { ACTION_TYPES, type ActionType } from "../api/types";

const ACTION_LABELS: Record<ActionType, string> = {
  call_customer: "Call customer",
  send_confirmation_sms: "Send confirmation SMS",
  send_reminder_email: "Send reminder email",
  flag_for_manual_review: "Flag for manual review",
  convert_cod_to_prepaid: "Convert COD to prepaid",
};

export default function InterventionActionForm({ orderId }: { orderId: string }) {
  const { actorName } = useApp();
  const [actionType, setActionType] = useState<ActionType>("call_customer");
  const [note, setNote] = useState("");
  const mutation = useCreateAction(orderId);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate(
      { action_type: actionType, note: note || undefined, actor_name: actorName || undefined },
      { onSuccess: () => setNote("") },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded border border-neutral-200 p-3 dark:border-neutral-800">
      <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Log an intervention</h3>
      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Action</label>
        <select
          value={actionType}
          onChange={(e) => setActionType(e.target.value as ActionType)}
          className="mt-1 w-full rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          {ACTION_TYPES.map((a) => (
            <option key={a} value={a}>{ACTION_LABELS[a]}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Note (optional)</label>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          className="mt-1 w-full rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
      </div>
      <button
        type="submit"
        disabled={mutation.isPending}
        className="rounded bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
      >
        {mutation.isPending ? "Logging…" : "Log action"}
      </button>
      {mutation.isError && <p className="text-xs text-red-600 dark:text-red-400">{(mutation.error as Error).message}</p>}
    </form>
  );
}
