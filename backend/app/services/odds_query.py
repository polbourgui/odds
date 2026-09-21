"""Shared low-level odds queries used by both the value bets and event
comparison services."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.odds import OddsSnapshot


def as_utc(value: datetime) -> datetime:
    # SQLite (used in tests) drops tzinfo on round-trip even for
    # DateTime(timezone=True) columns; Postgres (production) does not, so
    # this is a no-op there. Values are stored/produced in UTC throughout.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def latest_snapshots(db: Session) -> Sequence[OddsSnapshot]:
    """One row per (selection_id, bookmaker_id): its most recent snapshot."""
    row_number = (
        func.row_number()
        .over(
            partition_by=(OddsSnapshot.selection_id, OddsSnapshot.bookmaker_id),
            order_by=OddsSnapshot.captured_at.desc(),
        )
        .label("rn")
    )
    subq = select(OddsSnapshot, row_number).subquery()
    latest = aliased(OddsSnapshot, subq)
    stmt = select(latest).where(subq.c.rn == 1)
    return db.scalars(stmt).all()
