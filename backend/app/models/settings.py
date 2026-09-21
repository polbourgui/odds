from sqlalchemy import Enum, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DevigMethod


class AppSettings(Base):
    """Singleton row holding the user-tunable calculation parameters.

    A row with id=1 is the only one expected to exist; enforced at the
    service layer rather than the DB to keep this schema simple.
    """

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    devig_method: Mapped[DevigMethod] = mapped_column(
        Enum(DevigMethod, name="devig_method"), default=DevigMethod.MULTIPLICATIVE, nullable=False
    )
    kelly_fraction: Mapped[float] = mapped_column(Numeric(4, 3), default=0.25, nullable=False)
    kelly_cap_pct: Mapped[float] = mapped_column(Numeric(4, 3), default=0.02, nullable=False)
    edge_threshold: Mapped[float] = mapped_column(Numeric(5, 4), default=0.03, nullable=False)
    stale_odds_minutes: Mapped[int] = mapped_column(default=10, nullable=False)

    default_bankroll: Mapped[float] = mapped_column(Numeric(12, 2), default=1000, nullable=False)
    monthly_loss_limit: Mapped[float | None] = mapped_column(Numeric(12, 2))

    def __repr__(self) -> str:
        return "<AppSettings>"
