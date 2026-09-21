"""Standalone background worker: runs scheduled jobs (currently just
closing-line capture) on an interval.

Deployed as its own process, separate from the FastAPI web app (see
README's deployment notes: a Render background worker service). It is
deliberately not wired into FastAPI's lifespan, so importing/running the
API and its test suite never starts a real scheduler thread against a live
database.

Run with: python -m app.scheduler
"""

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from app.core.config import get_settings
from app.db.session import SessionLocal
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


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        closing_capture_job,
        "interval",
        minutes=settings.closing_capture_interval_minutes,
        next_run_time=datetime.now(UTC),
    )
    logger.info(
        "Scheduler started: closing-line capture every %d minute(s)",
        settings.closing_capture_interval_minutes,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
