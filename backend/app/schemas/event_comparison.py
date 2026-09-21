from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import MarketType, SelectionCode


class ComparisonQuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bookmaker_slug: str
    bookmaker_name: str
    is_sharp_reference: bool
    is_anj_licensed: bool
    odds: float
    captured_at: datetime
    is_stale: bool
    is_best: bool
    deviation_vs_reference: float | None


class ComparisonSelectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    selection_code: SelectionCode
    participant_name: str | None
    reference_odds: float | None
    fair_odds: float | None
    true_probability: float | None
    quotes: list[ComparisonQuoteOut]


class ComparisonMarketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    market_type: MarketType
    line: float | None
    selections: list[ComparisonSelectionOut]


class EventComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: int
    sport_slug: str
    competition_name: str
    home_name: str
    away_name: str
    start_time: datetime
    markets: list[ComparisonMarketOut]
