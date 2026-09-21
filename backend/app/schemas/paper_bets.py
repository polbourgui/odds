from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BetStatus, DevigMethod, MarketType, SelectionCode


class BankrollOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    currency: str
    initial_balance: float
    current_balance: float


class BankrollUpdateIn(BaseModel):
    name: str | None = None
    initial_balance: float | None = Field(default=None, ge=0)


class PlaceBetIn(BaseModel):
    selection_id: int
    bookmaker_slug: str


class SettleBetIn(BaseModel):
    status: BetStatus


class PaperBetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bankroll_id: int

    sport_slug: str
    competition_name: str
    home_name: str
    away_name: str
    event_start_time: datetime

    market_type: MarketType
    line: float | None
    selection_code: SelectionCode
    participant_name: str | None

    bookmaker_slug: str
    bookmaker_name: str

    odds_taken: float
    stake: float
    true_probability_at_placement: float
    fair_odds_at_placement: float
    edge_at_placement: float
    devig_method_at_placement: DevigMethod

    placed_at: datetime
    closing_odds: float | None
    clv: float | None

    status: BetStatus
    settled_at: datetime | None
    payout: float | None
