import { useState } from "react";
import { useApp } from "../context/AppContext";
import { useCreateRule, useEvaluateRules, useRules, useUpdateRule } from "../api/hooks";
import { ACTION_TYPES, type ActionType } from "../api/types";

const ACTION_LABELS: Record<ActionType, string> = {
  call_customer: "Call customer",
  send_confirmation_sms: "Send confirmation SMS",
  send_reminder_email: "Send reminder email",
  flag_for_manual_review: "Flag for manual review",
  convert_cod_to_prepaid: "Convert COD to prepaid",
};

export default function RulesForm() {
  const { tenant } = useApp();
  const { data: rules, isLoading } = useRules();
  const createRule = useCreateRule();
  const updateRule = useUpdateRule();
  const evaluateRules = useEvaluateRules();

  const [name, setName] = useState("");
  const [threshold, setThreshold] = useState(0.75);
  const [actionType, setActionType] = useState<ActionType>("flag_for_manual_review");

  if (!tenant) {
    return (
      <p className="text-sm text-neutral-500 dark:text-neutral-400">
        Select a specific tenant (top-left) to view and manage its automated rules.
      </p>
    );
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    createRule.mutate(
      { name, score_threshold: threshold, action_type: actionType },
      { onSuccess: () => setName("") },
    );
  }

  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="flex flex-wrap items-end gap-3 rounded border border-neutral-200 p-3 dark:border-neutral-800">
        <div>
          <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Rule name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. High-risk auto-flag"
            className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">
            Threshold: {threshold.toFixed(2)}
          </label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            className="mt-2 w-32"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Action</label>
          <select
            value={actionType}
            onChange={(e) => setActionType(e.target.value as ActionType)}
            className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          >
            {ACTION_TYPES.map((a) => (
              <option key={a} value={a}>{ACTION_LABELS[a]}</option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          disabled={createRule.isPending || !name.trim()}
          className="rounded bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
        >
          Add rule
        </button>
        <button
          type="button"
          onClick={() => evaluateRules.mutate()}
          disabled={evaluateRules.isPending}
          className="rounded border border-neutral-300 px-3 py-1.5 text-sm font-medium hover:bg-neutral-100 disabled:opacity-40 dark:border-neutral-700 dark:hover:bg-neutral-800"
        >
          {evaluateRules.isPending ? "Running…" : "Run rule sweep now"}
        </button>
      </form>

      {evaluateRules.data && (
        <p className="text-sm text-neutral-600 dark:text-neutral-300">
          Sweep complete: {evaluateRules.data.rules_evaluated} active rule(s) evaluated,{" "}
          {evaluateRules.data.actions_created} new automated action(s) created.
        </p>
      )}

      {isLoading ? (
        <p className="text-sm text-neutral-500">Loading rules…</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
            <tr>
              <th className="px-2 py-1 font-medium">Name</th>
              <th className="px-2 py-1 font-medium">Threshold</th>
              <th className="px-2 py-1 font-medium">Action</th>
              <th className="px-2 py-1 font-medium">Active</th>
            </tr>
          </thead>
          <tbody>
            {(rules ?? []).map((r) => (
              <tr key={r.id} className="border-t border-neutral-100 dark:border-neutral-800">
                <td className="px-2 py-1.5">{r.name}</td>
                <td className="px-2 py-1.5 tabular-nums">{r.score_threshold.toFixed(2)}</td>
                <td className="px-2 py-1.5">{ACTION_LABELS[r.action_type]}</td>
                <td className="px-2 py-1.5">
                  <button
                    type="button"
                    onClick={() => updateRule.mutate({ ruleId: r.id, body: { is_active: !r.is_active } })}
                    className={`rounded px-2 py-0.5 text-xs font-medium ${
                      r.is_active
                        ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                        : "bg-neutral-100 text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400"
                    }`}
                  >
                    {r.is_active ? "Active" : "Inactive"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
