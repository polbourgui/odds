import secrets

from fastapi import Depends, Header, HTTPException

from app.core.config import Settings, get_settings


def require_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Reject requests missing a valid X-API-Key header, once one is configured.

    A no-op when Settings.api_key is empty, so local development needs no
    extra setup — only a public deployment is expected to set API_KEY.
    """
    if not settings.api_key:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Clé API invalide ou manquante")
