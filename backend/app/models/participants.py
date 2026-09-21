from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.sports import Competition


class Participant(Base):
    """A team (football, basketball, ...) or an individual player (tennis)."""

    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    aliases: Mapped[list["ParticipantAlias"]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Participant {self.name}>"


class ParticipantAlias(Base):
    """Editable mapping from a raw provider name to a canonical participant.

    Used to reconcile events across odds sources whose team/player naming
    conventions differ (e.g. "Man Utd" vs "Manchester United").
    """

    __tablename__ = "participant_aliases"
    __table_args__ = (
        # Scoped by sport too: a short raw name (e.g. "Miami") from the same
        # provider can refer to a different participant in a different sport.
        UniqueConstraint(
            "provider", "raw_name", "sport_id", name="uq_participant_alias_provider_raw_sport"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), nullable=False)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_name: Mapped[str] = mapped_column(String(150), nullable=False)

    participant: Mapped[Participant] = relationship(back_populates="aliases")

    def __repr__(self) -> str:
        return f"<ParticipantAlias {self.provider}:{self.raw_name}>"


class CompetitionAlias(Base):
    """Editable mapping from a raw provider competition name to a canonical one."""

    __tablename__ = "competition_aliases"
    __table_args__ = (
        UniqueConstraint("provider", "raw_name", name="uq_competition_alias_provider_raw"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_name: Mapped[str] = mapped_column(String(150), nullable=False)

    competition: Mapped["Competition"] = relationship()

    def __repr__(self) -> str:
        return f"<CompetitionAlias {self.provider}:{self.raw_name}>"
