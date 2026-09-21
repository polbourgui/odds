from sqlalchemy import Enum, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MarketType, SelectionCode


class EventMarket(Base):
    """A specific market offered on an event (e.g. 1X2, or Over/Under 2.5)."""

    __tablename__ = "event_markets"
    __table_args__ = (
        UniqueConstraint("event_id", "market_type", "line", name="uq_event_market_type_line"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    market_type: Mapped[MarketType] = mapped_column(
        Enum(MarketType, name="market_type"), nullable=False
    )

    # Total line for over/under markets (e.g. 2.5 goals). Null for 1X2/moneyline.
    line: Mapped[float | None] = mapped_column(Numeric(6, 2))

    event: Mapped["Event"] = relationship(back_populates="markets")  # noqa: F821
    selections: Mapped[list["Selection"]] = relationship(
        back_populates="event_market", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EventMarket {self.market_type} event={self.event_id}>"


class Selection(Base):
    """A single outcome of a market that can be priced by bookmakers."""

    __tablename__ = "selections"
    __table_args__ = (
        UniqueConstraint(
            "event_market_id", "code", "participant_id", name="uq_selection_market_code_participant"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_market_id: Mapped[int] = mapped_column(ForeignKey("event_markets.id"), nullable=False)
    code: Mapped[SelectionCode] = mapped_column(
        Enum(SelectionCode, name="selection_code"), nullable=False
    )

    # Set only for moneyline participant-win selections (tennis, NBA winner).
    participant_id: Mapped[int | None] = mapped_column(ForeignKey("participants.id"))

    event_market: Mapped[EventMarket] = relationship(back_populates="selections")
    participant: Mapped["Participant | None"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return f"<Selection {self.code} market={self.event_market_id}>"
