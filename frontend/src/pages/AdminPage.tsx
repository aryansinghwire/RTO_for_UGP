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

export default function AdminPage() {
  const { role } = useApp();
  const canManage = role === "ops_manager" || role === "admin";

  return (
    <div className="space-y-8 p-4">
      <h2 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">Admin</h2>

      <TenantSection />

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Automated rules</h3>
        {canManage ? (
          <RulesForm />
        ) : (
          <p className="text-xs text-neutral-400">Managing rules requires Ops Manager or Admin.</p>
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Audit log</h3>
        {canManage ? (
          <AuditLogTable />
        ) : (
          <p className="text-xs text-neutral-400">Viewing the audit log requires Ops Manager or Admin.</p>
        )}
      </section>
    </div>
  );
}
