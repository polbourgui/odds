from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import MarketType
from app.schemas.value_bets import ValueBetOut
from app.services.app_settings import get_effective_settings
from app.services.value_bets import compute_value_bets

router = APIRouter(prefix="/api", tags=["value-bets"])


@router.get("/value-bets", response_model=list[ValueBetOut])
def list_value_bets(
    sport: str | None = Query(None, description="Sport slug filter, e.g. 'soccer'"),
    market: MarketType | None = Query(None, description="Market type filter"),
    bookmaker: str | None = Query(None, description="Bookmaker slug filter"),
    edge_min: float | None = Query(None, description="Minimum edge as a fraction, e.g. 0.03"),
    db: Session = Depends(get_db),
) -> list[ValueBetOut]:
    value_bets = compute_value_bets(
        db,
        settings=get_effective_settings(db),
        sport_slug=sport,
        market_type=market,
        bookmaker_slug=bookmaker,
        edge_min=edge_min,
    )
    return [ValueBetOut.model_validate(vb) for vb in value_bets]
