from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BankrollPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    at: datetime
    balance: float
    label: str


class GroupStatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    bets: int
    profit: float
    turnover: float
    roi: float | None


class StatsSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_bets: int
    pending_bets: int
    graded_bets: int
    wins: int
    losses: int
    pushes: int
    voids: int

    win_rate: float | None
    win_rate_ci: tuple[float, float] | None

    turnover: float
    profit: float
    roi: float | None
    roi_ci: tuple[float, float] | None

    average_clv: float | None
    average_clv_ci: tuple[float, float] | None
    clv_sample_size: int

    max_drawdown_pct: float | None
    bankroll_curve: list[BankrollPointOut]
    by_bookmaker: list[GroupStatOut]
    by_sport: list[GroupStatOut]
    by_market: list[GroupStatOut]

    monthly_profit: float
    monthly_loss_limit: float | None
    monthly_loss_limit_reached: bool
