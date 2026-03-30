from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime
import httpx

from app.database import get_db
from app.models import (
    Match, League, Bookmaker, Odds,
    ArbitrageOpportunity, MatchStatus, Notification
)
from app import schemas
from app.dependencies import get_active_api_key, use_api_key, detect_arbitrage

router = APIRouter(prefix="/odds", tags=["Odds"])


@router.get("/", response_model=List[schemas.OddsResponse])
def get_latest_odds(db: Session = Depends(get_db)):
    """Get the most recent odds for every upcoming match."""
    subquery = (
        db.query(Odds.match_id, func.max(Odds.fetched_at).label("latest"))
        .group_by(Odds.match_id)
        .subquery()
    )
    return (
        db.query(Odds)
        .join(subquery, (Odds.match_id == subquery.c.match_id) &
              (Odds.fetched_at == subquery.c.latest))
        .all()
    )


@router.get("/{match_id}", response_model=List[schemas.OddsResponse])
def get_match_odds(match_id: str, db: Session = Depends(get_db)):
    """Get all bookmaker odds for a specific match."""
    return db.query(Odds).filter(Odds.match_id == match_id).all()


@router.post("/fetch")
def fetch_odds(db: Session = Depends(get_db)):
    """
    Fetch fresh odds from the-odds-api.com.
    Runs automatically on a schedule but can also be triggered manually.
    Stores all odds historically and detects arbitrage opportunities.
    """
    api_key = get_active_api_key(db)
    bookmakers = db.query(Bookmaker).filter(Bookmaker.is_active == True).all()
    bookmaker_keys = ",".join([b.api_key for b in bookmakers if b.api_key])
    leagues = db.query(League).all()

    new_odds_count = 0
    opportunities_found = 0

    with httpx.Client() as client:
        for league in leagues:
            url = (
                f"https://api.the-odds-api.com/v4/sports/{league.key}/odds"
                f"?apiKey={api_key.key}"
                f"&regions=eu"
                f"&markets=h2h"
                f"&bookmakers={bookmaker_keys}"
            )
            response = client.get(url)
            use_api_key(api_key, db)

            if response.status_code != 200:
                continue

            data = response.json()

            for event in data:
                # Get or create match
                match = db.query(Match).filter(Match.id == event["id"]).first()
                if not match:
                    match = Match(
                        id=event["id"],
                        league_id=league.id,
                        home_team=event["home_team"],
                        away_team=event["away_team"],
                        kick_off=datetime.fromisoformat(
                            event["commence_time"].replace("Z", "+00:00")
                        ),
                        status=MatchStatus.upcoming
                    )
                    db.add(match)
                    db.commit()

                # Track best odds per outcome across all bookmakers for arbitrage detection
                best = {"home": 0.0, "draw": 0.0, "away": 0.0}
                best_bm = {"home": None, "draw": None, "away": None}

                for bookmaker_data in event.get("bookmakers", []):
                    # Match by api_key field for reliable lookup
                    bm = db.query(Bookmaker).filter(
                        Bookmaker.api_key == bookmaker_data["key"]
                    ).first()
                    if not bm:
                        continue

                    outcomes = {
                        o["name"]: o["price"]
                        for o in bookmaker_data["markets"][0]["outcomes"]
                    }
                    home = outcomes.get(event["home_team"], 0)
                    draw = outcomes.get("Draw", 0)
                    away = outcomes.get(event["away_team"], 0)

                    if not all([home, draw, away]):
                        continue

                    db.add(Odds(
                        match_id=match.id,
                        bookmaker_id=bm.id,
                        home=home,
                        draw=draw,
                        away=away
                    ))
                    new_odds_count += 1

                    # Track best odds per outcome for arbitrage detection
                    if home > best["home"]:
                        best["home"] = home
                        best_bm["home"] = bm.id
                    if draw > best["draw"]:
                        best["draw"] = draw
                        best_bm["draw"] = bm.id
                    if away > best["away"]:
                        best["away"] = away
                        best_bm["away"] = bm.id

                # Check for arbitrage across best odds from all bookmakers
                if all([best["home"], best["draw"], best["away"]]):
                    margin = detect_arbitrage(best["home"], best["draw"], best["away"])
                    if margin:
                        db.add(ArbitrageOpportunity(
                            match_id=match.id,
                            home_odds=best["home"],
                            draw_odds=best["draw"],
                            away_odds=best["away"],
                            home_bookmaker_id=best_bm["home"],
                            draw_bookmaker_id=best_bm["draw"],
                            away_bookmaker_id=best_bm["away"],
                            margin_percent=margin
                        ))
                        # Create a notification for the new opportunity
                        db.add(Notification(
                            message=(
                                f"Arbitrage opportunity: {match.home_team} vs {match.away_team} "
                                f"— {margin:.2f}% guaranteed margin"
                            ),
                            type="arbitrage"
                        ))
                        opportunities_found += 1

            db.commit()

        # Notify if the active API key is running low
        requests_remaining = api_key.requests_limit - api_key.requests_used
        if requests_remaining <= 50:
            db.add(Notification(
                message=f"API key #{api_key.id} has only {requests_remaining} requests remaining.",
                type="api_key_low"
            ))
            db.commit()

    return {
        "new_odds_stored": new_odds_count,
        "arbitrage_opportunities_found": opportunities_found
    }
