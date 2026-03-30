from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.database import SessionLocal
from app.routers.odds import fetch_odds
from app.routers.results import check_results
from dotenv import load_dotenv
import logging
import os

load_dotenv()

logger = logging.getLogger(__name__)

# How often to run each job — configurable via .env
ODDS_FETCH_INTERVAL_HOURS = int(os.getenv("ODDS_FETCH_INTERVAL_HOURS", 4))
RESULTS_CHECK_INTERVAL_MINUTES = int(os.getenv("RESULTS_CHECK_INTERVAL_MINUTES", 30))


def scheduled_fetch_odds():
    """Fetch fresh odds and detect arbitrage. Runs on a configurable interval."""
    db = SessionLocal()
    try:
        result = fetch_odds(db)
        logger.info(
            f"Scheduled odds fetch complete — "
            f"{result['new_odds_stored']} odds stored, "
            f"{result['arbitrage_opportunities_found']} arbitrage opportunities found"
        )
    except Exception as e:
        logger.error(f"Scheduled odds fetch failed: {e}")
    finally:
        db.close()


def scheduled_check_results():
    """Check results for pending bets. Runs on a configurable interval."""
    db = SessionLocal()
    try:
        result = check_results(db)
        logger.info(
            f"Scheduled results check complete — "
            f"{result['legs_settled']} legs settled"
        )
    except Exception as e:
        logger.error(f"Scheduled results check failed: {e}")
    finally:
        db.close()


def start_scheduler():
    """
    Start the background scheduler.
    Called once when the API server starts.
    Intervals are read from .env so you can change them without touching code.
    """
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        scheduled_fetch_odds,
        trigger=IntervalTrigger(hours=ODDS_FETCH_INTERVAL_HOURS),
        id="fetch_odds",
        name="Fetch odds from the-odds-api.com",
        replace_existing=True
    )

    scheduler.add_job(
        scheduled_check_results,
        trigger=IntervalTrigger(minutes=RESULTS_CHECK_INTERVAL_MINUTES),
        id="check_results",
        name="Check results for pending bets",
        replace_existing=True
    )

    scheduler.start()
    logger.info(
        f"Scheduler started — "
        f"odds every {ODDS_FETCH_INTERVAL_HOURS}h, "
        f"results every {RESULTS_CHECK_INTERVAL_MINUTES}min"
    )
    return scheduler
