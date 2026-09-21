import type { MarketType, SelectionCode } from "./types";

export function formatOdds(value: number): string {
  return value.toFixed(2);
}

export function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatSignedPct(value: number): string {
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

export function formatStake(value: number): string {
  return value.toFixed(2);
}

export function formatKickoff(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatFreshness(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h`;
}

const MARKET_LABELS: Record<MarketType, string> = {
  "1x2": "1X2",
  moneyline: "Vainqueur",
  over_under: "Over/Under",
};

export function formatMarket(marketType: MarketType, line: number | null): string {
  const label = MARKET_LABELS[marketType] ?? marketType;
  return line !== null ? `${label} ${line}` : label;
}

const SELECTION_LABELS: Record<SelectionCode, string> = {
  home: "Domicile",
  draw: "Nul",
  away: "Extérieur",
  over: "Plus de",
  under: "Moins de",
  participant_win: "Vainqueur",
};

export function formatSelection(code: SelectionCode, participantName: string | null): string {
  if (code === "participant_win" && participantName) return participantName;
  return SELECTION_LABELS[code] ?? code;
}
