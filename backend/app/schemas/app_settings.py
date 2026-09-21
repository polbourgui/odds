from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DevigMethod


class AppSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    devig_method: DevigMethod
    kelly_fraction: float
    kelly_cap_pct: float
    edge_threshold: float
    stale_odds_minutes: int
    default_bankroll: float
    monthly_loss_limit: float | None


class AppSettingsUpdateIn(BaseModel):
    devig_method: DevigMethod | None = None
    kelly_fraction: float | None = Field(default=None, gt=0, le=1)
    kelly_cap_pct: float | None = Field(default=None, gt=0, le=1)
    edge_threshold: float | None = None
    stale_odds_minutes: int | None = Field(default=None, gt=0)
    default_bankroll: float | None = Field(default=None, ge=0)
    monthly_loss_limit: float | None = Field(default=None, ge=0)
