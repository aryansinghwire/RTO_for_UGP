import { useEffect } from "react";
import { useApp } from "../context/AppContext";
import { useRoles, useTenants } from "../api/hooks";
import type { Role } from "../api/types";

export default function RoleSwitcher() {
  const { role, setRole, actorName, setActorName, actorTenant, setActorTenant } = useApp();
  const { data: roles } = useRoles();
  const { data: tenants } = useTenants();

  // Becoming a Tenant Admin means belonging to a tenant, so default to the
  // first one rather than leaving the account in a tenantless state where
  // every scoped request would be rejected.
  useEffect(() => {
    if (role === "tenant_admin" && !actorTenant && tenants?.length) {
      setActorTenant(tenants[0].slug);
    }
  }, [role, actorTenant, tenants, setActorTenant]);

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
      {role === "tenant_admin" && (
        <div>
          <label htmlFor="actor-tenant" className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">
            Your tenant (simulated sign-in)
          </label>
          <select
            id="actor-tenant"
            value={actorTenant ?? ""}
            onChange={(e) => setActorTenant(e.target.value || null)}
            className="mt-1 w-full rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          >
            {(tenants ?? []).map((t) => (
              <option key={t.slug} value={t.slug}>
                {t.name}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
            Switching this is how you sign in as a different tenant's admin. You can only configure the
            tenant selected here.
          </p>
        </div>
      )}

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
