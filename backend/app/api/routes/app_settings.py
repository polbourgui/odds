from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.app_settings import AppSettingsOut, AppSettingsUpdateIn
from app.services.app_settings import (
    AppSettingsError,
    get_or_create_app_settings,
    update_app_settings,
)

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings", response_model=AppSettingsOut)
def get_settings_route(db: Session = Depends(get_db)) -> AppSettingsOut:
    row = get_or_create_app_settings(db)
    db.commit()
    return AppSettingsOut.model_validate(row)


@router.patch("/settings", response_model=AppSettingsOut)
def patch_settings_route(
    payload: AppSettingsUpdateIn, db: Session = Depends(get_db)
) -> AppSettingsOut:
    row = get_or_create_app_settings(db)
    updates = payload.model_dump(exclude_unset=True)
    try:
        row = update_app_settings(db, row, **updates)
    except AppSettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return AppSettingsOut.model_validate(row)
