import enum


class EventStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class MarketType(str, enum.Enum):
    ONE_X_TWO = "1x2"
    MONEYLINE = "moneyline"  # two-way winner market (tennis, NBA, ...)
    OVER_UNDER = "over_under"


class SelectionCode(str, enum.Enum):
    HOME = "home"
    DRAW = "draw"
    AWAY = "away"
    OVER = "over"
    UNDER = "under"
    PARTICIPANT_WIN = "participant_win"  # used with moneyline + participant_id


class DevigMethod(str, enum.Enum):
    MULTIPLICATIVE = "multiplicative"
    POWER = "power"
    SHIN = "shin"


class BetStatus(str, enum.Enum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    PUSH = "push"
    VOID = "void"
