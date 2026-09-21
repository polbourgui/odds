"""Standalone background worker: runs scheduled jobs (closing-line capture,
automatic settlement) on an interval.

Deployed as its own process, separate from the FastAPI web app (see
README's deployment notes: a Render background worker service). It is
deliberately not wired into FastAPI's lifespan, so importing/running the
API and its test suite never starts a real scheduler thread against a live
database.

Run with: python -m app.scheduler
"""

import logging
from datetime import UTC, datetime
from functools import partial

from apscheduler.schedulers.blocking import BlockingScheduler

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.providers.the_odds_api import TheOddsApiProvider
from app.services.auto_settlement import run_auto_settlement
from app.services.closing_capture import run_closing_capture

logger = logging.getLogger(__name__)


def closing_capture_job() -> None:
    db = SessionLocal()
    try:
        run_closing_capture(db)
    except Exception:
        logger.exception("Closing-line capture job failed")
    finally:
        db.close()


def auto_settlement_job(provider: TheOddsApiProvider) -> None:
    db = SessionLocal()
    try:
        run_auto_settlement(db, provider)
    except Exception:
        logger.exception("Auto-settlement job failed")
    finally:
        db.close()


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    results_provider = TheOddsApiProvider(settings=settings)

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        closing_capture_job,
        "interval",
        minutes=settings.closing_capture_interval_minutes,
        next_run_time=datetime.now(UTC),
    )
    scheduler.add_job(
        partial(auto_settlement_job, results_provider),
        "interval",
        minutes=settings.auto_settlement_interval_minutes,
        next_run_time=datetime.now(UTC),
    )
    logger.info(
        "Scheduler started: closing-line capture every %d min, auto-settlement every %d min",
        settings.closing_capture_interval_minutes,
        settings.auto_settlement_interval_minutes,
    )
    try:
        scheduler.start()
    finally:
        results_provider.close()


if __name__ == "__main__":
    main()
