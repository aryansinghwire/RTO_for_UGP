import { useState } from "react";
import { useApp } from "../context/AppContext";
import { useCreateTenant, useTenants } from "../api/hooks";
import RulesForm from "../components/RulesForm";
import AuditLogTable from "../components/AuditLogTable";

function TenantSection() {
  const { role } = useApp();
  const { data: tenants } = useTenants();
  const createTenant = useCreateTenant();
  const [name, setName] = useState("");

  return (
    <section className="space-y-3">
      <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
        Tenants <span className="font-normal text-neutral-400">(demo brands, simulated for the multi-tenant demo)</span>
      </h3>
      <ul className="space-y-1 text-sm">
        {(tenants ?? []).map((t) => (
          <li key={t.id} className="rounded border border-neutral-200 px-2 py-1 dark:border-neutral-800">
            {t.name} <span className="text-xs text-neutral-400">({t.slug})</span>
          </li>
        ))}
      </ul>
      {role === "admin" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!name.trim()) return;
            createTenant.mutate({ name }, { onSuccess: () => setName("") });
          }}
          className="flex items-end gap-2"
        >
          <div>
            <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">New tenant name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Meridian Living"
              className="mt-1 rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
            />
          </div>
          <button
            type="submit"
            disabled={createTenant.isPending || !name.trim()}
            className="rounded bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
          >
            Onboard tenant
          </button>
        </form>
      ) : (
        <p className="text-xs text-neutral-400">Onboarding a new tenant requires the Admin role.</p>
      )}
    </section>
  );
}

/** States plainly which tenant's configuration the current role is allowed to
 *  touch, so the page never looks like it is editing settings globally. */
function ScopeNotice() {
  const { role, actorTenant } = useApp();
  const { data: tenants } = useTenants();

  if (role === "admin") {
    return (
      <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
        <strong>Platform Admin.</strong> You are working across all tenants — the tenant selector at
        the top-left decides whose configuration you are editing.
      </p>
    );
  }

  const name = tenants?.find((t) => t.slug === actorTenant)?.name ?? actorTenant;
  return (
    <p className="rounded border border-teal-200 bg-teal-50 px-3 py-2 text-xs text-teal-900 dark:border-teal-900 dark:bg-teal-950 dark:text-teal-200">
      <strong>Tenant Admin{name ? ` — ${name}` : ""}.</strong> Score windows are configured per tenant.
      You can only see and change your own; other tenants' settings are not reachable from this account.
    </p>
  );
}

export default function AdminPage() {
  const { role } = useApp();
  const canManage = role === "tenant_admin" || role === "admin";

  return (
    <div className="space-y-8 p-4">
      <h2 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">Admin</h2>

      <ScopeNotice />

      <TenantSection />

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
          Automated score windows
        </h3>
        {canManage ? (
          <RulesForm />
        ) : (
          <p className="text-xs text-neutral-400">Managing score windows requires Tenant Admin or Platform Admin.</p>
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Audit log</h3>
        {canManage ? (
          <AuditLogTable />
        ) : (
          <p className="text-xs text-neutral-400">Viewing the audit log requires Tenant Admin or Platform Admin.</p>
        )}
      </section>
    </div>
  );
}
