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
import { mockApi } from "../api/mockApi";
import { runtimeConfig } from "../config/runtime";
import type { Receipt } from "../models";

interface AppStateValue {
  api: AppApi;
  receipts: Receipt[];
  loading: boolean;
  error: string | null;
  refreshReceipts(): Promise<void>;
}

const AppStateContext = createContext<AppStateValue | null>(null);

export function AppStateProvider({ children }: PropsWithChildren): React.JSX.Element {
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const api = mockApi;

  const refreshReceipts = useCallback(async (): Promise<void> => {
    try {
      setError(null);
      setReceipts(await api.listReceipts());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load receipts.");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    if (runtimeConfig.mode === "mock") {
      void refreshReceipts();
    }
  }, [refreshReceipts]);

  const value = useMemo<AppStateValue>(
    () => ({ api, receipts, loading, error, refreshReceipts }),
    [api, receipts, loading, error, refreshReceipts],
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
