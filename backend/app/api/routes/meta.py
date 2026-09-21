from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.session import get_db
from app.models.bookmakers import Bookmaker
from app.models.sports import Sport
from app.schemas.meta import BookmakerOut, SportOut

router = APIRouter(prefix="/api", tags=["meta"], dependencies=[Depends(require_api_key)])


@router.get("/sports", response_model=list[SportOut])
def list_sports(db: Session = Depends(get_db)) -> list[SportOut]:
    sports = db.scalars(select(Sport).order_by(Sport.name)).all()
    return [SportOut.model_validate(s) for s in sports]


@router.get("/bookmakers", response_model=list[BookmakerOut])
def list_bookmakers(db: Session = Depends(get_db)) -> list[BookmakerOut]:
    bookmakers = db.scalars(
        select(Bookmaker)
        .where(Bookmaker.is_anj_licensed.is_(True), Bookmaker.active.is_(True))
        .order_by(Bookmaker.name)
    ).all()
    return [BookmakerOut.model_validate(b) for b in bookmakers]
