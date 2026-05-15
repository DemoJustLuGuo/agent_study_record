import { useCallback, useMemo, useState } from "react";
import { DEFAULT_ADMIN_TOKEN } from "../api/client";

const STORAGE_KEY = "agent-study-admin-token";

export function useAdminToken() {
  const [token, setTokenState] = useState(() => {
    if (DEFAULT_ADMIN_TOKEN) {
      return DEFAULT_ADMIN_TOKEN;
    }
    return window.localStorage.getItem(STORAGE_KEY) || "";
  });

  const setToken = useCallback((value: string) => {
    const next = value.trim();
    setTokenState(next);
    if (next) {
      window.localStorage.setItem(STORAGE_KEY, next);
      return;
    }
    window.localStorage.removeItem(STORAGE_KEY);
  }, []);

  return useMemo(
    () => ({
      token,
      setToken,
      isConfigured: Boolean(token),
      source: DEFAULT_ADMIN_TOKEN ? "env" : token ? "local" : "missing",
    }),
    [setToken, token]
  );
}
