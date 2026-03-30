from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.models import ApiKey, BetStatus, Bet


def get_active_api_key(db: Session) -> ApiKey:
    """
    Get the current active API key.
    Automatically moves to the next one if the current is used up.
    """
    key = db.query(ApiKey).filter(
        ApiKey.is_active == True,
        ApiKey.requests_used < ApiKey.requests_limit
    ).order_by(ApiKey.id).first()

    if not key:
        raise HTTPException(status_code=503, detail="No API keys available")
    return key


def use_api_key(key: ApiKey, db: Session):
    """Increment usage count on an API key after using it."""
    key.requests_used += 1
    key.last_used_at = datetime.utcnow()
    db.commit()


def detect_arbitrage(home: float, draw: float, away: float) -> Optional[float]:
    """
    Check if three odds represent an arbitrage opportunity.
    Returns the margin percent if profitable, None if not.
    An arbitrage exists when the sum of inverse odds is less than 1.
    """
    total = (1 / home) + (1 / draw) + (1 / away)
    if total < 1:
        margin = round((1 - total) * 100, 4)
        return margin
    return None


def calculate_potential_return(odds: List[float], stake: float) -> float:
    """
    Multiply all odds together and multiply by stake.
    For a single: odds * stake
    For a double: odds1 * odds2 * stake
    For a triple: odds1 * odds2 * odds3 * stake
    """
    combined = 1.0
    for o in odds:
        combined *= o
    return round(combined * stake, 2)


def settle_bet(bet: Bet, db: Session):
    """
    Evaluate all legs of a bet and mark the bet as won, lost or void.
    - Void: if any leg is void (e.g. match cancelled) — stake is returned
    - Won: all legs won
    - Lost: any leg lost
    Called automatically when match results come in.
    """
    leg_results = [leg.result for leg in bet.legs]

    if any(r == BetStatus.void for r in leg_results):
        bet.status = BetStatus.void
        bet.actual_return = bet.stake
    elif all(r == BetStatus.won for r in leg_results):
        bet.status = BetStatus.won
        bet.actual_return = bet.potential_return
    else:
        bet.status = BetStatus.lost
        bet.actual_return = 0.0

    bet.settled_at = datetime.utcnow()
    db.commit()
