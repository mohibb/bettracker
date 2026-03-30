from fastapi import FastAPI
from app.database import engine, Base
from app.routers import config, odds, matches, arbitrage, cart, bets, results, notifications

# Create all database tables on startup if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="BetTracker API",
    description="Virtual football betting tracker",
    version="1.0.0"
)

app.include_router(config.router)
app.include_router(odds.router)
app.include_router(matches.router)
app.include_router(arbitrage.router)
app.include_router(cart.router)
app.include_router(bets.router)
app.include_router(results.router)
app.include_router(notifications.router)
