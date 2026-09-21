import type { Bookmaker, Sport, ValueBet } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function getJSON<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`Request to ${path} failed: HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export interface ValueBetsFilters {
  sport?: string;
  market?: string;
  bookmaker?: string;
  edgeMin?: number;
}

export function fetchValueBets(filters: ValueBetsFilters = {}): Promise<ValueBet[]> {
  return getJSON<ValueBet[]>("/api/value-bets", {
    sport: filters.sport,
    market: filters.market,
    bookmaker: filters.bookmaker,
    edge_min: filters.edgeMin,
  });
}

export function fetchSports(): Promise<Sport[]> {
  return getJSON<Sport[]>("/api/sports");
}

export function fetchBookmakers(): Promise<Bookmaker[]> {
  return getJSON<Bookmaker[]>("/api/bookmakers");
}
