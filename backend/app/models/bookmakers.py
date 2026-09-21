from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Bookmaker(Base):
    __tablename__ = "bookmakers"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # ANJ-licensed French bookmaker (Winamax, Betclic, Unibet, ZEturf, PMU, ...)
    is_anj_licensed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Used as the sharp reference for devig / edge calculations (e.g. Pinnacle).
    is_sharp_reference: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Bookmaker {self.slug}>"
