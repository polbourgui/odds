"""Adapter for The Odds API (https://the-odds-api.com).

Chosen as the primary source per the brief: an aggregation API is preferred
over scraping bookmaker sites directly. Only the market types in scope for
V1 (1X2 / moneyline / over-under) are mapped; anything else (spreads,
props, ...) is silently skipped.
"""

import logging

import httpx

from app.core.config import Settings, get_settings
from app.models.enums import MarketType, SelectionCode
from app.providers.base import (
    OddsProvider,
    ProviderBookmakerQuote,
    ProviderEvent,
    ProviderEventOdds,
    ProviderMarket,
    ProviderOutcome,
    ProviderResult,
    ResultsProvider,
)
from app.providers.exceptions import (
    ProviderAuthError,
    ProviderQuotaExceededError,
    ProviderResponseError,
    ProviderTimeoutError,
)

logger = logging.getLogger(__name__)

# Provider market keys we understand. "spreads" and anything else are out of
# scope for V1 and are skipped rather than raising.
_SUPPORTED_ODDS_API_MARKETS = ("h2h", "totals")


def _parse_event(raw: dict, sport_key: str) -> ProviderEvent:
    return ProviderEvent(
        provider_event_id=raw["id"],
        sport_key=sport_key,
        competition_name=raw.get("sport_title", sport_key),
        home_name=raw["home_team"],
        away_name=raw["away_team"],
        start_time=raw["commence_time"],
    )


def _parse_h2h_market(raw_market: dict, home_name: str, away_name: str) -> ProviderMarket | None:
    outcomes_raw = raw_market.get("outcomes", [])
    names = {o["name"] for o in outcomes_raw}

    if "Draw" in names and len(outcomes_raw) == 3:
        market_type = MarketType.ONE_X_TWO
        outcomes = []
        for o in outcomes_raw:
            if o["name"] == home_name:
                code = SelectionCode.HOME
            elif o["name"] == away_name:
                code = SelectionCode.AWAY
            elif o["name"] == "Draw":
                code = SelectionCode.DRAW
            else:
                logger.warning("Unrecognized 1X2 outcome name %r, skipping", o["name"])
                continue
            outcomes.append(ProviderOutcome(selection_code=code, price=o["price"]))
        return ProviderMarket(market_type=market_type, outcomes=outcomes)

    if len(outcomes_raw) == 2:
        outcomes = [
            ProviderOutcome(
                selection_code=SelectionCode.PARTICIPANT_WIN,
                price=o["price"],
                participant_name=o["name"],
            )
            for o in outcomes_raw
        ]
        return ProviderMarket(market_type=MarketType.MONEYLINE, outcomes=outcomes)

    logger.warning("Unrecognized h2h market shape with %d outcomes, skipping", len(outcomes_raw))
    return None


def _parse_totals_market(raw_market: dict) -> ProviderMarket | None:
    outcomes = []
    for o in raw_market.get("outcomes", []):
        name = o["name"].strip().lower()
        if name == "over":
            code = SelectionCode.OVER
        elif name == "under":
            code = SelectionCode.UNDER
        else:
            logger.warning("Unrecognized totals outcome name %r, skipping", o["name"])
            continue
        outcomes.append(ProviderOutcome(selection_code=code, price=o["price"], line=o.get("point")))
    if not outcomes:
        return None
    return ProviderMarket(market_type=MarketType.OVER_UNDER, outcomes=outcomes)


def _parse_market(raw_market: dict, home_name: str, away_name: str) -> ProviderMarket | None:
    key = raw_market.get("key")
    if key == "h2h":
        return _parse_h2h_market(raw_market, home_name, away_name)
    if key == "totals":
        return _parse_totals_market(raw_market)
    return None


def _parse_result(raw: dict) -> ProviderResult:
    completed = bool(raw.get("completed"))
    home_score: float | None = None
    away_score: float | None = None

    if completed and raw.get("scores"):
        by_name = {s["name"]: s.get("score") for s in raw["scores"]}
        home_raw = by_name.get(raw.get("home_team"))
        away_raw = by_name.get(raw.get("away_team"))
        try:
            home_score = float(home_raw) if home_raw is not None else None
            away_score = float(away_raw) if away_raw is not None else None
        except (TypeError, ValueError):
            logger.warning("Could not parse scores for event id=%r", raw.get("id"))

    return ProviderResult(
        provider_event_id=raw["id"],
        completed=completed,
        home_score=home_score,
        away_score=away_score,
    )


def _parse_event_odds(raw: dict, sport_key: str) -> ProviderEventOdds:
    event = _parse_event(raw, sport_key)
    bookmakers = []
    for raw_bm in raw.get("bookmakers", []):
        markets = [
            m
            for raw_market in raw_bm.get("markets", [])
            if raw_market.get("key") in _SUPPORTED_ODDS_API_MARKETS
            and (m := _parse_market(raw_market, event.home_name, event.away_name)) is not None
        ]
        if not markets:
            continue
        bookmakers.append(
            ProviderBookmakerQuote(
                bookmaker_key=raw_bm["key"],
                bookmaker_name=raw_bm.get("title", raw_bm["key"]),
                last_update=raw_bm.get("last_update") or raw["commence_time"],
                markets=markets,
            )
        )
    return ProviderEventOdds(event=event, bookmakers=bookmakers)


class TheOddsApiProvider(OddsProvider, ResultsProvider):
    name = "the_odds_api"

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self._settings = settings or get_settings()
        if not self._settings.odds_api_key:
            logger.warning("ODDS_API_KEY is not set; requests to The Odds API will fail")
        self._client = client or httpx.Client(
            base_url=self._settings.odds_api_base_url,
            timeout=self._settings.odds_api_timeout_seconds,
        )

    def _get(self, path: str, params: dict) -> object:
        params = {**params, "apiKey": self._settings.odds_api_key}
        try:
            response = self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            logger.error("The Odds API request to %s timed out", path)
            raise ProviderTimeoutError(f"Request to {path} timed out") from exc
        except httpx.HTTPError as exc:
            logger.error("The Odds API request to %s failed: %s", path, exc)
            raise ProviderResponseError(f"Request to {path} failed: {exc}") from exc

        remaining = response.headers.get("x-requests-remaining")

        if response.status_code in (401, 403):
            logger.error("The Odds API auth error on %s: HTTP %s", path, response.status_code)
            raise ProviderAuthError(
                f"Authentication failed for {path} (HTTP {response.status_code})"
            )

        if response.status_code == 429:
            logger.error("The Odds API quota exceeded on %s (remaining=%s)", path, remaining)
            raise ProviderQuotaExceededError(
                f"Quota exceeded for {path}",
                requests_remaining=int(remaining) if remaining is not None else None,
            )

        if response.status_code >= 400:
            logger.error(
                "The Odds API error on %s: HTTP %s — %s",
                path,
                response.status_code,
                response.text[:500],
            )
            raise ProviderResponseError(f"HTTP {response.status_code} from {path}")

        if remaining is not None:
            logger.info("The Odds API requests remaining after %s: %s", path, remaining)

        try:
            return response.json()
        except ValueError as exc:
            raise ProviderResponseError(f"Invalid JSON from {path}") from exc

    def fetch_events(self, sport_key: str) -> list[ProviderEvent]:
        raw_events = self._get(f"/sports/{sport_key}/events", params={})
        return [_parse_event(raw, sport_key) for raw in raw_events]

    def fetch_odds(
        self, sport_key: str, market_types: list[MarketType] | None = None
    ) -> list[ProviderEventOdds]:
        params = {
            "regions": self._settings.odds_api_regions,
            "markets": "h2h,totals",
            "oddsFormat": "decimal",
        }
        raw_events = self._get(f"/sports/{sport_key}/odds", params=params)
        results = [_parse_event_odds(raw, sport_key) for raw in raw_events]
        if market_types is not None:
            wanted = set(market_types)
            for event_odds in results:
                for bm in event_odds.bookmakers:
                    bm.markets = [m for m in bm.markets if m.market_type in wanted]
        return results

    def fetch_results(
        self, sport_key: str, event_ids: list[str] | None = None
    ) -> list[ProviderResult]:
        params = {"daysFrom": self._settings.odds_api_scores_days_from}
        if event_ids:
            params["eventIds"] = ",".join(event_ids)
        raw_results = self._get(f"/sports/{sport_key}/scores", params=params)
        return [_parse_result(raw) for raw in raw_results]

    def close(self) -> None:
        self._client.close()
