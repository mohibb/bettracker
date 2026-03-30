from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import httpx

from app.database import get_db
from app.models import (
    Match, BetLeg, Bet, Notification,
    BetStatus, MatchStatus, MatchResult
)
from app.dependencies import get_active_api_key, use_api_key, settle_bet

router = APIRouter(prefix="/results", tags=["Results"])


@router.post("/check")
def check_results(db: Session = Depends(get_db)):
    """
    Fetch results for all pending bets on finished matches.
    Settles each bet leg and then the parent bet automatically.
    Runs on a schedule but can also be triggered manually.
    """
    api_key = get_active_api_key(db)

    # Find all pending legs
    pending_legs = (
        db.query(BetLeg)
        .join(Match)
        .filter(BetLeg.result == BetStatus.pending)
        .all()
    )

    match_ids = list(set(leg.match_id for leg in pending_legs))
    settled_count = 0

    with httpx.Client() as client:
        for match_id in match_ids:
            match = db.query(Match).filter(Match.id == match_id).first()
            if not match:
                continue

            url = (
                f"https://api.the-odds-api.com/v4/sports/{match.league.key}"
                f"/scores/?apiKey={api_key.key}&daysFrom=3"
            )
            response = client.get(url)
            use_api_key(api_key, db)

            if response.status_code != 200:
                continue

            scores = response.json()
            event = next((s for s in scores if s["id"] == match_id), None)

            # Skip if not completed yet
            if not event or not event.get("completed"):
                continue

            # Parse scores
            home_score = next(
                (int(s["score"]) for s in event["scores"]
                 if s["name"] == match.home_team), None
            )
            away_score = next(
                (int(s["score"]) for s in event["scores"]
                 if s["name"] == match.away_team), None
            )
            if home_score is None or away_score is None:
                continue

            # Determine result
            if home_score > away_score:
                result = MatchResult.home
            elif away_score > home_score:
                result = MatchResult.away
            else:
                result = MatchResult.draw

            # Update match record
            match.home_goals = home_score
            match.away_goals = away_score
            match.result = result
            match.status = MatchStatus.finished

            # Settle each pending leg for this match
            for leg in pending_legs:
                if leg.match_id != match_id:
                    continue
                leg.result = (
                    BetStatus.won
                    if leg.selection.value == result.value
                    else BetStatus.lost
                )
                settled_count += 1

            db.commit()

            # Settle any parent bets where all legs are now resolved
            affected_bet_ids = list(set(
                leg.bet_id for leg in pending_legs
                if leg.match_id == match_id
            ))
            for bet_id in affected_bet_ids:
                bet = db.query(Bet).filter(Bet.id == bet_id).first()
                if bet and all(l.result != BetStatus.pending for l in bet.legs):
                    settle_bet(bet, db)
                    # Create a notification for the settled bet
                    outcome = "won" if bet.status == BetStatus.won else "lost"
                    db.add(Notification(
                        message=(
                            f"Bet #{bet.id} ({bet.type.value}) has been settled — you {outcome}. "
                            f"Return: {bet.actual_return:.2f}"
                        ),
                        type="bet_settled"
                    ))
            db.commit()

    return {"legs_settled": settled_count}


@router.get("/{match_id}")
def get_result(match_id: str, db: Session = Depends(get_db)):
    """Get the result for a specific match."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return {
        "match_id": match.id,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "home_goals": match.home_goals,
        "away_goals": match.away_goals,
        "result": match.result,
        "status": match.status
    }
