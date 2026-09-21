export type MarketType = "1x2" | "moneyline" | "over_under";

export type SelectionCode =
  | "home"
  | "draw"
  | "away"
  | "over"
  | "under"
  | "participant_win";

export interface ValueBet {
  event_id: number;
  sport_slug: string;
  competition_name: string;
  home_name: string;
  away_name: string;
  start_time: string;

  market_type: MarketType;
  line: number | null;
  selection_code: SelectionCode;
  participant_name: string | null;

  bookmaker_slug: string;
  bookmaker_name: string;

  book_odds: number;
  fair_odds: number;
  true_probability: number;
  edge: number;
  kelly_stake: number;

  captured_at: string;
  reference_captured_at: string;
}

export interface Sport {
  slug: string;
  name: string;
}

export interface Bookmaker {
  slug: string;
  name: string;
  is_anj_licensed: boolean;
}
