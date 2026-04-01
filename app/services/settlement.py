from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Bet, BetStatus


def settle_bet(bet: Bet, db: Session) -> None:
    """
    Evaluate all legs and mark the bet as won, lost, or void.

    Rules:
      - Void:  any leg is void (e.g. match cancelled) — stake is returned
      - Won:   all legs won
      - Lost:  any leg lost (and none void)

    Called automatically when match results arrive via results router.
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
