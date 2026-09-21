from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import MarketType, SelectionCode


class ValueBetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: int
    sport_slug: str
    competition_name: str
    home_name: str
    away_name: str
    start_time: datetime

    market_type: MarketType
    line: float | None
    selection_code: SelectionCode
    participant_name: str | None

    bookmaker_slug: str
    bookmaker_name: str

    book_odds: float
    fair_odds: float
    true_probability: float
    edge: float
    kelly_stake: float

    captured_at: datetime
    reference_captured_at: datetime
