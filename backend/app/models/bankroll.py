from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import BetStatus, DevigMethod


class Bankroll(Base):
    """A virtual (paper) bankroll. Real money is never involved."""

    __tablename__ = "bankrolls"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    initial_balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    current_balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    bets: Mapped[list["PaperBet"]] = relationship(back_populates="bankroll")

    def __repr__(self) -> str:
        return f"<Bankroll {self.name}>"


class PaperBet(Base):
    """A fictitious bet: odds, stake and edge are frozen at placement time."""

    __tablename__ = "paper_bets"

    id: Mapped[int] = mapped_column(primary_key=True)
    bankroll_id: Mapped[int] = mapped_column(ForeignKey("bankrolls.id"), nullable=False)
    selection_id: Mapped[int] = mapped_column(ForeignKey("selections.id"), nullable=False)
    bookmaker_id: Mapped[int] = mapped_column(ForeignKey("bookmakers.id"), nullable=False)

    # Frozen at placement time.
    odds_taken: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    stake: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    true_probability_at_placement: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    fair_odds_at_placement: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    edge_at_placement: Mapped[float] = mapped_column(Numeric(7, 5), nullable=False)
    devig_method_at_placement: Mapped[DevigMethod] = mapped_column(
        Enum(DevigMethod, name="devig_method_bet"), nullable=False
    )

    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Captured automatically at kickoff for CLV computation.
    closing_odds: Mapped[float | None] = mapped_column(Numeric(10, 3))
    clv: Mapped[float | None] = mapped_column(Numeric(7, 5))

    status: Mapped[BetStatus] = mapped_column(
        Enum(BetStatus, name="bet_status"), default=BetStatus.PENDING, nullable=False
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payout: Mapped[float | None] = mapped_column(Numeric(12, 2))

    bankroll: Mapped[Bankroll] = relationship(back_populates="bets")
    selection: Mapped["Selection"] = relationship()  # noqa: F821
    bookmaker: Mapped["Bookmaker"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return f"<PaperBet {self.id} status={self.status}>"
