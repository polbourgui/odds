"""DB-backed, runtime-editable overrides for the user-tunable calculation
parameters (Réglages page), layered on top of the environment-sourced
`Settings`. Editing them takes effect immediately -- every request re-reads
the singleton row, no process restart needed. Infra-level settings (DB URL,
API keys, CORS origins, ...) stay environment-only.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.enums import DevigMethod
from app.models.settings import AppSettings

_VALID_DEVIG_METHODS = {m.value for m in DevigMethod}

_UPDATABLE_FIELDS = {
    "devig_method",
    "kelly_fraction",
    "kelly_cap_pct",
    "edge_threshold",
    "stale_odds_minutes",
    "default_bankroll",
    "monthly_loss_limit",
}


class AppSettingsError(ValueError):
    """An app settings update was invalid."""


def get_or_create_app_settings(db: Session, *, env_settings: Settings | None = None) -> AppSettings:
    env_settings = env_settings or get_settings()
    row = db.scalars(select(AppSettings).order_by(AppSettings.id)).first()
    if row is not None:
        return row
    row = AppSettings(
        devig_method=DevigMethod(env_settings.devig_method),
        kelly_fraction=env_settings.kelly_fraction,
        kelly_cap_pct=env_settings.kelly_cap_pct,
        edge_threshold=env_settings.edge_threshold,
        stale_odds_minutes=env_settings.stale_odds_minutes,
        default_bankroll=env_settings.default_bankroll,
        monthly_loss_limit=env_settings.monthly_loss_limit,
    )
    db.add(row)
    db.flush()
    return row


def update_app_settings(db: Session, row: AppSettings, **fields: object) -> AppSettings:
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise AppSettingsError(f"Champ(s) de réglage inconnu(s) : {', '.join(sorted(unknown))}")

    # Every field but monthly_loss_limit is NOT NULL in the DB; reject an
    # explicit null early rather than letting it fail as a raw IntegrityError.
    for key, value in fields.items():
        if key != "monthly_loss_limit" and value is None:
            raise AppSettingsError(f"{key} ne peut pas être vide")

    devig_method = fields.get("devig_method")
    if devig_method is not None:
        if devig_method not in _VALID_DEVIG_METHODS:
            raise AppSettingsError(f"devig_method invalide : {devig_method}")
        fields["devig_method"] = DevigMethod(devig_method)

    kelly_fraction = fields.get("kelly_fraction")
    if kelly_fraction is not None and not (0 < kelly_fraction <= 1):
        raise AppSettingsError("kelly_fraction doit être dans (0, 1]")

    kelly_cap_pct = fields.get("kelly_cap_pct")
    if kelly_cap_pct is not None and not (0 < kelly_cap_pct <= 1):
        raise AppSettingsError("kelly_cap_pct doit être dans (0, 1]")

    stale_odds_minutes = fields.get("stale_odds_minutes")
    if stale_odds_minutes is not None and stale_odds_minutes <= 0:
        raise AppSettingsError("stale_odds_minutes doit être positif")

    default_bankroll = fields.get("default_bankroll")
    if default_bankroll is not None and default_bankroll < 0:
        raise AppSettingsError("default_bankroll ne peut pas être négatif")

    if "monthly_loss_limit" in fields and fields["monthly_loss_limit"] is not None:
        if fields["monthly_loss_limit"] < 0:
            raise AppSettingsError("monthly_loss_limit ne peut pas être négatif")

    for key, value in fields.items():
        setattr(row, key, value)
    db.flush()
    return row


def get_effective_settings(db: Session, *, env_settings: Settings | None = None) -> Settings:
    """The env-sourced Settings, with the user-tunable fields overridden by
    whatever is stored in the Réglages-page-editable AppSettings singleton."""
    env_settings = env_settings or get_settings()
    row = get_or_create_app_settings(db, env_settings=env_settings)
    return env_settings.model_copy(
        update={
            "devig_method": row.devig_method.value,
            "kelly_fraction": float(row.kelly_fraction),
            "kelly_cap_pct": float(row.kelly_cap_pct),
            "edge_threshold": float(row.edge_threshold),
            "stale_odds_minutes": row.stale_odds_minutes,
            "default_bankroll": float(row.default_bankroll),
            "monthly_loss_limit": (
                float(row.monthly_loss_limit) if row.monthly_loss_limit is not None else None
            ),
        }
    )
