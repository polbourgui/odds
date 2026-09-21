from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EventStatus


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"), nullable=False)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False)

    home_participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), nullable=False)
    away_participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), nullable=False)

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status"), default=EventStatus.SCHEDULED, nullable=False
    )

    # External identifier from the primary odds provider, kept for debugging/traceability.
    external_ref: Mapped[str | None] = mapped_column(String(150))

    sport: Mapped["Sport"] = relationship()  # noqa: F821
    competition: Mapped["Competition"] = relationship()  # noqa: F821
    home_participant: Mapped["Participant"] = relationship(  # noqa: F821
        foreign_keys=[home_participant_id]
    )
    away_participant: Mapped["Participant"] = relationship(  # noqa: F821
        foreign_keys=[away_participant_id]
    )
    markets: Mapped[list["EventMarket"]] = relationship(  # noqa: F821
        back_populates="event", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Event {self.id} @ {self.start_time}>"
