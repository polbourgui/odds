from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.event_comparison import EventComparisonOut
from app.services.app_settings import get_effective_settings
from app.services.event_comparison import get_event_comparison

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events/{event_id}/comparison", response_model=EventComparisonOut)
def get_comparison(event_id: int, db: Session = Depends(get_db)) -> EventComparisonOut:
    comparison = get_event_comparison(db, event_id, settings=get_effective_settings(db))
    if comparison is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventComparisonOut.model_validate(comparison)
