import type {
  AppSettings,
  AppSettingsUpdate,
  Bankroll,
  BetStatus,
  Bookmaker,
  EventComparison,
  PaperBet,
  Sport,
  StatsSummary,
  ValueBet,
} from "../types";

// Same-origin by default, so a production build served by the backend
// itself (install.sh's local self-hosted setup) needs no configuration
// regardless of which host/port it ends up running on. Local dev (Vite on
// :5173, API on :8000) overrides this via VITE_API_BASE_URL in .env.local.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || window.location.origin;
const API_KEY = import.meta.env.VITE_API_KEY;

function authHeaders(): HeadersInit {
  return API_KEY ? { "X-API-Key": API_KEY } : {};
}

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
  const response = await fetch(url.toString(), { headers: authHeaders() });
  if (!response.ok) {
    throw new Error(`Request to ${path} failed: HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function sendJSON<T>(path: string, method: "POST" | "PATCH", body?: unknown): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  const response = await fetch(url.toString(), {
    method,
    headers: { "Content-Type": "application/json", ...authHeaders() },
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
  const response = await fetch(url.toString(), { headers: authHeaders() });
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

export function fetchAppSettings(): Promise<AppSettings> {
  return getJSON<AppSettings>("/api/settings");
}

export function updateAppSettings(payload: AppSettingsUpdate): Promise<AppSettings> {
  return sendJSON<AppSettings>("/api/settings", "PATCH", payload);
}

export function fetchStats(): Promise<StatsSummary> {
  return getJSON<StatsSummary>("/api/stats");
}

export async function downloadPaperBetsCsv(): Promise<void> {
  const url = new URL("/api/paper-bets/export.csv", API_BASE_URL);
  const response = await fetch(url.toString(), { headers: authHeaders() });
  if (!response.ok) {
    throw new ApiError(`Export CSV échoué : HTTP ${response.status}`, response.status);
  }
  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = "paper_bets.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(blobUrl);
}
