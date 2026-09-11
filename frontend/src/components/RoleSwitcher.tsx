import { useApp } from "../context/AppContext";
import { useRoles } from "../api/hooks";
import type { Role } from "../api/types";

export default function RoleSwitcher() {
  const { role, setRole, actorName, setActorName } = useApp();
  const { data: roles } = useRoles();

  return (
    <div className="space-y-2">
      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">
          Role (simulated)
        </label>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as Role)}
          className="mt-1 w-full rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          {(roles ?? []).map((r) => (
            <option key={r.role} value={r.role}>
              {r.label}
            </option>
          ))}
        </select>
        {roles && (
          <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
            {roles.find((r) => r.role === role)?.description}
          </p>
        )}
      </div>
      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Your name</label>
        <input
          type="text"
          value={actorName}
          onChange={(e) => setActorName(e.target.value)}
          placeholder="e.g. Priya"
          className="mt-1 w-full rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
        <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
          Recorded against actions/overrides you take.
        </p>
      </div>
    </div>
  );
}
