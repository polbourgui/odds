from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Sport(Base):
    __tablename__ = "sports"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    competitions: Mapped[list["Competition"]] = relationship(back_populates="sport")

    def __repr__(self) -> str:
        return f"<Sport {self.slug}>"


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100))

    # The provider's own sport_key (e.g. "soccer_epl"), needed to query a
    # results feed for automatic settlement -- more specific than Sport.slug,
    # which is only the general category ("soccer").
    provider_sport_key: Mapped[str | None] = mapped_column(String(100))

    sport: Mapped[Sport] = relationship(back_populates="competitions")

    def __repr__(self) -> str:
        return f"<Competition {self.slug}>"
