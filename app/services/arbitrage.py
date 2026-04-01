from typing import Optional


def detect_arbitrage(home: float, draw: float, away: float) -> Optional[float]:
    """
    Check if three odds represent an arbitrage opportunity.
    Returns the margin percent (> 0) if profitable, None otherwise.

    An arbitrage exists when the sum of inverse odds across bookmakers is < 1.
    The margin is how much guaranteed profit exists as a percentage of stakes.
    """
    total = (1 / home) + (1 / draw) + (1 / away)
    if total < 1:
        return round((1 - total) * 100, 4)
    return None


def calculate_potential_return(odds: list[float], stake: float) -> float:
    """
    Calculate potential return for a multi-leg bet.

    Multiplies all odds together, then by the stake:
      single:  odds * stake
      double:  odds1 * odds2 * stake
      triple:  odds1 * odds2 * odds3 * stake
    """
    combined = 1.0
    for o in odds:
        combined *= o
    return round(combined * stake, 2)
