from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import engine, Base
from app.routers import config, odds, matches, arbitrage, cart, bets, results, notifications, leagues
from app.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup and shutdown."""
    Base.metadata.create_all(bind=engine)
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()


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
app.include_router(leagues.router)
