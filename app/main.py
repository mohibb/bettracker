from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import engine, Base
from app.routers import config, odds, matches, arbitrage, cart, bets, results, notifications
from app.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app):
    """Runs on startup and shutdown."""
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()


# Create all database tables on startup if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="BetTracker API",
    description="Virtual football betting tracker",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(config.router)
app.include_router(odds.router)
app.include_router(matches.router)
app.include_router(arbitrage.router)
app.include_router(cart.router)
app.include_router(bets.router)
app.include_router(results.router)
app.include_router(notifications.router)
