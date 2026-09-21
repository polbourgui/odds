class ProviderError(Exception):
    """Base class for all odds-provider errors."""


class ProviderAuthError(ProviderError):
    """Invalid or missing API key (HTTP 401/403)."""


class ProviderQuotaExceededError(ProviderError):
    """The provider's request quota has been exhausted (HTTP 429)."""

    def __init__(self, message: str, *, requests_remaining: int | None = None):
        super().__init__(message)
        self.requests_remaining = requests_remaining


class ProviderTimeoutError(ProviderError):
    """The provider did not respond in time."""


class ProviderResponseError(ProviderError):
    """The provider returned a response we could not parse."""
