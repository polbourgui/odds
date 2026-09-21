from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.session import get_db
from app.models.enums import BetStatus
from app.schemas.paper_bets import (
    BankrollOut,
    BankrollUpdateIn,
    PaperBetOut,
    PlaceBetIn,
    SettleBetIn,
)
from app.services.app_settings import get_effective_settings
from app.services.paper_bets import (
    PaperBettingError,
    export_paper_bets_csv,
    get_or_create_default_bankroll,
    list_paper_bets,
    place_paper_bet,
    reset_bankroll,
    settle_paper_bet,
    to_paper_bet_view,
    update_bankroll,
)

router = APIRouter(prefix="/api", tags=["paper-bets"], dependencies=[Depends(require_api_key)])


@router.get("/bankroll", response_model=BankrollOut)
def get_bankroll(db: Session = Depends(get_db)) -> BankrollOut:
    bankroll = get_or_create_default_bankroll(db)
    db.commit()
    return BankrollOut.model_validate(bankroll)


@router.patch("/bankroll", response_model=BankrollOut)
def patch_bankroll(payload: BankrollUpdateIn, db: Session = Depends(get_db)) -> BankrollOut:
    bankroll = get_or_create_default_bankroll(db)
    try:
        bankroll = update_bankroll(
            db, bankroll, name=payload.name, initial_balance=payload.initial_balance
        )
    except PaperBettingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return BankrollOut.model_validate(bankroll)


@router.post("/bankroll/reset", response_model=BankrollOut)
def post_reset_bankroll(db: Session = Depends(get_db)) -> BankrollOut:
    bankroll = get_or_create_default_bankroll(db)
    bankroll = reset_bankroll(db, bankroll)
    db.commit()
    return BankrollOut.model_validate(bankroll)


@router.get("/paper-bets", response_model=list[PaperBetOut])
def get_paper_bets(
    status: BetStatus | None = Query(None), db: Session = Depends(get_db)
) -> list[PaperBetOut]:
    views = list_paper_bets(db, status=status)
    return [PaperBetOut.model_validate(v) for v in views]


@router.get("/paper-bets/export.csv")
def export_paper_bets(db: Session = Depends(get_db)) -> Response:
    csv_text = export_paper_bets_csv(db)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_bets.csv"},
    )


@router.post("/paper-bets", response_model=PaperBetOut, status_code=201)
def post_paper_bet(payload: PlaceBetIn, db: Session = Depends(get_db)) -> PaperBetOut:
    try:
        bet = place_paper_bet(
            db,
            selection_id=payload.selection_id,
            bookmaker_slug=payload.bookmaker_slug,
            settings=get_effective_settings(db),
        )
    except PaperBettingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PaperBetOut.model_validate(to_paper_bet_view(bet))


@router.post("/paper-bets/{bet_id}/settle", response_model=PaperBetOut)
def post_settle_paper_bet(
    bet_id: int, payload: SettleBetIn, db: Session = Depends(get_db)
) -> PaperBetOut:
    try:
        bet = settle_paper_bet(db, bet_id=bet_id, status=payload.status)
    except PaperBettingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PaperBetOut.model_validate(to_paper_bet_view(bet))
