import { NavLink } from "react-router-dom";
import { useApp } from "../context/AppContext";
import { useTenants } from "../api/hooks";
import RoleSwitcher from "./RoleSwitcher";

const linkBase =
  "block rounded px-3 py-2 text-sm font-medium transition-colors";
const linkActive = "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900";
const linkInactive =
  "text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800";

export default function NavSidebar() {
  const { tenant, setTenant, role } = useApp();
  const { data: tenants } = useTenants();
  const canSeeAdmin = role !== "ops_analyst";

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col gap-6 overflow-y-auto border-r border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-800 dark:bg-neutral-950">
      <div>
        <h1 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">RTO Risk Engine</h1>
        <p className="text-xs text-neutral-500 dark:text-neutral-400">Ops dashboard prototype</p>
      </div>

      <div>
        <label className="block text-xs font-medium text-neutral-500 dark:text-neutral-400">Tenant</label>
        <select
          value={tenant ?? ""}
          onChange={(e) => setTenant(e.target.value || null)}
          className="mt-1 w-full rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          <option value="">All tenants</option>
          {(tenants ?? []).map((t) => (
            <option key={t.slug} value={t.slug}>
              {t.name}
            </option>
          ))}
        </select>
      </div>

      <nav className="flex flex-col gap-1">
        <NavLink to="/queue" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}>
          Queue
        </NavLink>
        <NavLink to="/reporting" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}>
          Reporting
        </NavLink>
        <NavLink to="/alerts" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}>
          Alerts
        </NavLink>
        {canSeeAdmin && (
          <NavLink to="/admin" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}>
            Admin
          </NavLink>
        )}
      </nav>

      <div className="mt-auto border-t border-neutral-200 pt-4 dark:border-neutral-800">
        <RoleSwitcher />
      </div>
    </aside>
  );
}
