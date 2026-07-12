import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import type { AppApi } from "../api/appApi";
import { mockApi, setMockUser } from "../api/mockApi";
import { runtimeConfig } from "../config/runtime";
import { SEEDED_USERS } from "../data/seed";
import type { AppUser, Invoice } from "../models";

interface AppStateValue {
  api: AppApi;
  availableUsers: AppUser[];
  currentUser: AppUser | null;
  invoices: Invoice[];
  loading: boolean;
  error: string | null;
  refresh(): Promise<void>;
  switchUser(userId: string): Promise<void>;
}

const AppStateContext = createContext<AppStateValue | null>(null);

export function AppStateProvider({ children }: PropsWithChildren): React.JSX.Element {
  const api = mockApi;
  const [currentUser, setCurrentUser] = useState<AppUser | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (): Promise<void> => {
    try {
      setError(null);
      const [user, visibleInvoices] = await Promise.all([api.getMe(), api.listInvoices()]);
      setCurrentUser(user);
      setInvoices(visibleInvoices);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load invoices.");
    } finally {
      setLoading(false);
    }
  }, [api]);

  const switchUser = useCallback(
    async (userId: string): Promise<void> => {
      setLoading(true);
      setMockUser(userId);
      await refresh();
    },
    [refresh],
  );

  useEffect(() => {
    if (runtimeConfig.mode === "mock") {
      void refresh();
    }
  }, [refresh]);

  const value = useMemo<AppStateValue>(
    () => ({
      api,
      availableUsers: SEEDED_USERS,
      currentUser,
      invoices,
      loading,
      error,
      refresh,
      switchUser,
    }),
    [api, currentUser, invoices, loading, error, refresh, switchUser],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppStateValue {
  const value = useContext(AppStateContext);
  if (!value) {
    throw new Error("useAppState must be used inside AppStateProvider.");
  }
  return value;
}
