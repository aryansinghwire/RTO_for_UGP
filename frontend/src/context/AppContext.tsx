import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ROLE_LEVELS, type Role } from "../api/types";

interface AppContextValue {
  role: Role;
  setRole: (role: Role) => void;
  tenant: string | null; // tenant slug being viewed; null = "all tenants"
  setTenant: (tenant: string | null) => void;
  /** The tenant the signed-in user belongs to. A real deployment would read
   *  this off the session; here it's picked in the role switcher so the
   *  tenant-isolation rules can be demonstrated from either side. */
  actorTenant: string | null;
  setActorTenant: (tenant: string | null) => void;
  actorName: string;
  setActorName: (name: string) => void;
}

const AppContext = createContext<AppContextValue | undefined>(undefined);

const STORAGE_KEYS = {
  role: "rto-dashboard.role",
  tenant: "rto-dashboard.tenant",
  actorTenant: "rto-dashboard.actorTenant",
  actorName: "rto-dashboard.actorName",
};

function readStored<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw !== null ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeStored<T>(key: string, value: T) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore (e.g. private browsing storage restrictions)
  }
}

/** The "ops_manager" role was renamed to "tenant_admin". A browser that used
 *  the dashboard before the rename still has the old value in localStorage,
 *  and sending it as X-Role would 403 every request - so retire it on read. */
function readStoredRole(): Role {
  const stored = readStored<string>(STORAGE_KEYS.role, "ops_analyst");
  if (stored === "ops_manager") return "tenant_admin";
  return stored in ROLE_LEVELS ? (stored as Role) : "ops_analyst";
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<Role>(readStoredRole);
  const [tenant, setTenant] = useState<string | null>(() => readStored(STORAGE_KEYS.tenant, null));
  const [actorTenant, setActorTenant] = useState<string | null>(() =>
    readStored(STORAGE_KEYS.actorTenant, null),
  );
  const [actorName, setActorName] = useState<string>(() => readStored(STORAGE_KEYS.actorName, ""));

  // A Tenant Admin administers exactly one tenant, so the tenant being viewed
  // follows the one they're signed in as rather than being set separately.
  useEffect(() => {
    if (role === "tenant_admin" && actorTenant && tenant !== actorTenant) {
      setTenant(actorTenant);
    }
  }, [role, actorTenant, tenant]);

  useEffect(() => writeStored(STORAGE_KEYS.role, role), [role]);
  useEffect(() => writeStored(STORAGE_KEYS.tenant, tenant), [tenant]);
  useEffect(() => writeStored(STORAGE_KEYS.actorTenant, actorTenant), [actorTenant]);
  useEffect(() => writeStored(STORAGE_KEYS.actorName, actorName), [actorName]);

  const value = useMemo(
    () => ({ role, setRole, tenant, setTenant, actorTenant, setActorTenant, actorName, setActorName }),
    [role, tenant, actorTenant, actorName],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
