import { useState } from "react";
import { useApp } from "../context/AppContext";
import { useCreateRule, useEvaluateRules, useRules, useUpdateRule } from "../api/hooks";
import { ACTION_TYPES, type ActionType, type RuleOut } from "../api/types";
import ScoreRangeSlider from "./ScoreRangeSlider";

const ACTION_LABELS: Record<ActionType, string> = {
  call_customer: "Call customer",
  send_confirmation_sms: "Send confirmation SMS",
  send_reminder_email: "Send reminder email",
  flag_for_manual_review: "Flag for manual review",
  convert_cod_to_prepaid: "Convert COD to prepaid",
};

/** Inline window editor on an existing rule. Held in local state so dragging a
 *  thumb doesn't fire a request per pixel - it commits on release. */
function RuleWindowCell({ rule, canEdit }: { rule: RuleOut; canEdit: boolean }) {
  const updateRule = useUpdateRule();
  const [draft, setDraft] = useState<{ min: number; max: number } | null>(null);
  const window = draft ?? { min: rule.score_min, max: rule.score_max };

  function commit() {
    if (!draft) return;
    if (draft.min === rule.score_min && draft.max === rule.score_max) {
      setDraft(null);
      return;
    }
    updateRule.mutate(
      { ruleId: rule.id, body: { score_min: draft.min, score_max: draft.max } },
      { onSettled: () => setDraft(null) },
    );
  }

  if (!canEdit) {
    return (
      <span className="font-mono text-xs tabular-nums">
        {rule.score_min.toFixed(2)} – {rule.score_max.toFixed(2)}
      </span>
    );
  }

  return (
    <div onPointerUp={commit} onBlur={commit}>
      <ScoreRangeSlider
        label="Applies to scores"
        min={window.min}
        max={window.max}
        disabled={updateRule.isPending}
        onChange={setDraft}
      />
    </div>
  );
}

export default function RulesForm() {
  const { tenant, actorTenant, role } = useApp();
  const { data: rules, isLoading } = useRules();
  const createRule = useCreateRule();
  const updateRule = useUpdateRule();
  const evaluateRules = useEvaluateRules();

  const [name, setName] = useState("");
  const [window, setWindow] = useState({ min: 0.75, max: 1.0 });
  const [actionType, setActionType] = useState<ActionType>("flag_for_manual_review");

  // A tenant-scoped user always acts on their own tenant; only the platform
  // admin has to pick one, because they can address any of them.
  const targetTenant = role === "admin" ? tenant : actorTenant;

  if (!targetTenant) {
    return (
      <p className="text-sm text-neutral-500 dark:text-neutral-400">
        {role === "admin"
          ? "Select a specific tenant (top-left) to view and manage its score windows — rules belong to one tenant at a time."
          : "Choose which tenant you are signed in as (bottom-left) to manage its score windows."}
      </p>
    );
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    createRule.mutate(
      { name, score_min: window.min, score_max: window.max, action_type: actionType },
      { onSuccess: () => setName("") },
    );
  }

  const visible = rules ?? [];

  return (
    <div className="space-y-4">
      <form
        onSubmit={submit}
        className="flex flex-wrap items-end gap-x-6 gap-y-4 rounded border border-neutral-200 p-3 dark:border-neutral-800"
      >
        <div>
          <label htmlFor="rule-name" className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">
            Rule name
          </label>
          <input
            id="rule-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. High-risk auto-flag"
            className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          />
        </div>

        <ScoreRangeSlider label="Applies to scores" min={window.min} max={window.max} onChange={setWindow} />

        <div>
          <label htmlFor="rule-action" className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">
            Action
          </label>
          <select
            id="rule-action"
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

      <p className="text-xs text-neutral-500 dark:text-neutral-400">
        A rule fires on orders whose current score falls <em>inside</em> the window, so a tenant can send a
        cheap reminder in the 0.50–0.75 band and reserve a phone call for 0.90–1.00 without the two overlapping.
      </p>

      {(createRule.error || updateRule.error) && (
        <p className="text-sm text-rose-600 dark:text-rose-400">
          {(createRule.error ?? updateRule.error)?.message}
        </p>
      )}

      {evaluateRules.data && (
        <p className="text-sm text-neutral-600 dark:text-neutral-300">
          Sweep complete: {evaluateRules.data.rules_evaluated} active rule(s) evaluated,{" "}
          {evaluateRules.data.actions_created} new automated action(s) created.
        </p>
      )}

      {isLoading ? (
        <p className="text-sm text-neutral-500">Loading rules…</p>
      ) : visible.length === 0 ? (
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          No score windows configured for this tenant yet.
        </p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
            <tr>
              <th className="px-2 py-1 font-medium">Name</th>
              <th className="px-2 py-1 font-medium">Applies to scores</th>
              <th className="px-2 py-1 font-medium">Action</th>
              <th className="px-2 py-1 font-medium">Active</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr key={r.id} className="border-t border-neutral-100 align-top dark:border-neutral-800">
                <td className="px-2 py-3">
                  {r.name}
                  <span className="block text-xs text-neutral-400">{r.tenant}</span>
                </td>
                <td className="px-2 py-3">
                  <RuleWindowCell rule={r} canEdit={role === "admin" || r.tenant_slug === actorTenant} />
                </td>
                <td className="px-2 py-3">{ACTION_LABELS[r.action_type]}</td>
                <td className="px-2 py-3">
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
