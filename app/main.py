from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import config, odds, matches, arbitrage, cart, bets, results, notifications
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

# Allow requests from any origin — safe for a personal local app.
# Tighten this if you ever expose it publicly via Cloudflare.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)
app.include_router(odds.router)
app.include_router(matches.router)
app.include_router(arbitrage.router)
app.include_router(cart.router)
app.include_router(bets.router)
app.include_router(results.router)
app.include_router(notifications.router)