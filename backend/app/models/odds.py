from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OddsSnapshot(Base):
    """A single price quote for a selection at a bookmaker, at a point in time.

    Odds are never overwritten in place: every fetch inserts a new snapshot so
    the full price history is preserved, which is required to compute CLV.
    """

    __tablename__ = "odds_snapshots"
    __table_args__ = (
        Index(
            "ix_odds_snapshots_selection_bookmaker_time",
            "selection_id",
            "bookmaker_id",
            "captured_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    selection_id: Mapped[int] = mapped_column(ForeignKey("selections.id"), nullable=False)
    bookmaker_id: Mapped[int] = mapped_column(ForeignKey("bookmakers.id"), nullable=False)

    odds: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # True for the last snapshot captured at/after the event's kickoff, used as
    # the closing line reference for CLV.
    is_closing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    selection: Mapped["Selection"] = relationship()  # noqa: F821
    bookmaker: Mapped["Bookmaker"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return f"<OddsSnapshot sel={self.selection_id} book={self.bookmaker_id} odds={self.odds}>"
