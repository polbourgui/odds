import { useCallback, useEffect, useState } from "react";
import { fetchValueBets, type ValueBetsFilters } from "../api/client";
import type { ValueBet } from "../types";

const REFRESH_INTERVAL_MS = 30_000;

interface UseValueBetsResult {
  valueBets: ValueBet[];
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  refresh: () => void;
}

export function useValueBets(filters: ValueBetsFilters): UseValueBetsResult {
  const [valueBets, setValueBets] = useState<ValueBet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  const refresh = useCallback(() => setRefreshToken((n) => n + 1), []);
  const filtersKey = JSON.stringify(filters);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchValueBets(filters)
      .then((data) => {
        if (cancelled) return;
        setValueBets(data);
        setError(null);
        setLastUpdated(new Date());
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Erreur inconnue");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey, refreshToken]);

  useEffect(() => {
    const id = window.setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [refresh]);

  return { valueBets, loading, error, lastUpdated, refresh };
}
