from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.session import get_db
from app.schemas.stats import StatsSummaryOut
from app.services.app_settings import get_effective_settings
from app.services.stats import compute_stats

router = APIRouter(prefix="/api", tags=["stats"], dependencies=[Depends(require_api_key)])


@router.get("/stats", response_model=StatsSummaryOut)
def get_stats(db: Session = Depends(get_db)) -> StatsSummaryOut:
    summary = compute_stats(db, settings=get_effective_settings(db))
    db.commit()
    return StatsSummaryOut.model_validate(summary)
