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

export type DevigMethod = "multiplicative" | "power" | "shin";

export interface AppSettings {
  devig_method: DevigMethod;
  kelly_fraction: number;
  kelly_cap_pct: number;
  edge_threshold: number;
  stale_odds_minutes: number;
  default_bankroll: number;
  monthly_loss_limit: number | null;
}

export interface AppSettingsUpdate {
  devig_method?: DevigMethod;
  kelly_fraction?: number;
  kelly_cap_pct?: number;
  edge_threshold?: number;
  stale_odds_minutes?: number;
  default_bankroll?: number;
  monthly_loss_limit?: number | null;
}

export interface BankrollPoint {
  at: string;
  balance: number;
  label: string;
}

export interface GroupStat {
  key: string;
  label: string;
  bets: number;
  profit: number;
  turnover: number;
  roi: number | null;
}

export interface StatsSummary {
  total_bets: number;
  pending_bets: number;
  graded_bets: number;
  wins: number;
  losses: number;
  pushes: number;
  voids: number;

  win_rate: number | null;
  win_rate_ci: [number, number] | null;

  turnover: number;
  profit: number;
  roi: number | null;
  roi_ci: [number, number] | null;

  average_clv: number | null;
  average_clv_ci: [number, number] | null;
  clv_sample_size: number;

  max_drawdown_pct: number | null;
  bankroll_curve: BankrollPoint[];
  by_bookmaker: GroupStat[];
  by_sport: GroupStat[];
  by_market: GroupStat[];

  monthly_profit: number;
  monthly_loss_limit: number | null;
  monthly_loss_limit_reached: boolean;
}
