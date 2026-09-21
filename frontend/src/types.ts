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
  selection_id: number;
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

export interface ComparisonQuote {
  bookmaker_slug: string;
  bookmaker_name: string;
  is_sharp_reference: boolean;
  is_anj_licensed: boolean;
  odds: number;
  captured_at: string;
  is_stale: boolean;
  is_best: boolean;
  deviation_vs_reference: number | null;
}

export interface ComparisonSelection {
  selection_code: SelectionCode;
  participant_name: string | null;
  reference_odds: number | null;
  fair_odds: number | null;
  true_probability: number | null;
  quotes: ComparisonQuote[];
}

export interface ComparisonMarket {
  market_type: MarketType;
  line: number | null;
  selections: ComparisonSelection[];
}

export interface EventComparison {
  event_id: number;
  sport_slug: string;
  competition_name: string;
  home_name: string;
  away_name: string;
  start_time: string;
  markets: ComparisonMarket[];
}

export type BetStatus = "pending" | "won" | "lost" | "push" | "void";

export interface Bankroll {
  id: number;
  name: string;
  currency: string;
  initial_balance: number;
  current_balance: number;
}

export interface PaperBet {
  id: number;
  bankroll_id: number;

  sport_slug: string;
  competition_name: string;
  home_name: string;
  away_name: string;
  event_start_time: string;

  market_type: MarketType;
  line: number | null;
  selection_code: SelectionCode;
  participant_name: string | null;

  bookmaker_slug: string;
  bookmaker_name: string;

  odds_taken: number;
  stake: number;
  true_probability_at_placement: number;
  fair_odds_at_placement: number;
  edge_at_placement: number;

  placed_at: string;
  closing_odds: number | null;
  clv: number | null;

  status: BetStatus;
  settled_at: string | null;
  payout: number | null;
}
