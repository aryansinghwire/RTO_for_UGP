import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Role } from "../api/types";

interface AppContextValue {
  role: Role;
  setRole: (role: Role) => void;
  tenant: string | null; // tenant slug; null = "all tenants"
  setTenant: (tenant: string | null) => void;
  actorName: string;
  setActorName: (name: string) => void;
}

const AppContext = createContext<AppContextValue | undefined>(undefined);

const STORAGE_KEYS = {
  role: "rto-dashboard.role",
  tenant: "rto-dashboard.tenant",
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

export function AppProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<Role>(() => readStored(STORAGE_KEYS.role, "ops_analyst"));
  const [tenant, setTenant] = useState<string | null>(() => readStored(STORAGE_KEYS.tenant, null));
  const [actorName, setActorName] = useState<string>(() => readStored(STORAGE_KEYS.actorName, ""));

  useEffect(() => writeStored(STORAGE_KEYS.role, role), [role]);
  useEffect(() => writeStored(STORAGE_KEYS.tenant, tenant), [tenant]);
  useEffect(() => writeStored(STORAGE_KEYS.actorName, actorName), [actorName]);

  const value = useMemo(
    () => ({ role, setRole, tenant, setTenant, actorName, setActorName }),
    [role, tenant, actorName],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
