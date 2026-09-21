import type { Bankroll, BetStatus, Bookmaker, EventComparison, PaperBet, Sport, ValueBet } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

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

async function sendJSON<T>(path: string, method: "POST" | "PATCH", body?: unknown): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  const response = await fetch(url.toString(), {
    method,
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      // response body wasn't JSON; keep the generic message
    }
    throw new ApiError(detail, response.status);
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

export async function fetchEventComparison(eventId: number): Promise<EventComparison | null> {
  const url = new URL(`/api/events/${eventId}/comparison`, API_BASE_URL);
  const response = await fetch(url.toString());
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Request to /api/events/${eventId}/comparison failed: HTTP ${response.status}`);
  }
  return response.json() as Promise<EventComparison>;
}

export function fetchBankroll(): Promise<Bankroll> {
  return getJSON<Bankroll>("/api/bankroll");
}

export function updateBankroll(payload: {
  name?: string;
  initial_balance?: number;
}): Promise<Bankroll> {
  return sendJSON<Bankroll>("/api/bankroll", "PATCH", payload);
}

export function resetBankroll(): Promise<Bankroll> {
  return sendJSON<Bankroll>("/api/bankroll/reset", "POST");
}

export function fetchPaperBets(status?: BetStatus): Promise<PaperBet[]> {
  return getJSON<PaperBet[]>("/api/paper-bets", { status });
}

export function placePaperBet(selectionId: number, bookmakerSlug: string): Promise<PaperBet> {
  return sendJSON<PaperBet>("/api/paper-bets", "POST", {
    selection_id: selectionId,
    bookmaker_slug: bookmakerSlug,
  });
}

export function settlePaperBet(betId: number, status: BetStatus): Promise<PaperBet> {
  return sendJSON<PaperBet>(`/api/paper-bets/${betId}/settle`, "POST", { status });
}
