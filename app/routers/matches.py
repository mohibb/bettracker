from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import Match, Odds, MatchStatus
from app import schemas

router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get("/", response_model=List[schemas.MatchResponse])
def get_matches(
    league_id: Optional[int] = None,
    status: Optional[MatchStatus] = None,
    db: Session = Depends(get_db)
):
    """
    List all matches.
    Optionally filter by league_id or status (upcoming / live / finished / cancelled).
    """
    query = db.query(Match)
    if league_id:
        query = query.filter(Match.league_id == league_id)
    if status:
        query = query.filter(Match.status == status)
    return query.order_by(Match.kick_off).all()


@router.get("/{id}", response_model=schemas.MatchResponse)
def get_match(id: str, db: Session = Depends(get_db)):
    """Get a single match by ID including its current odds."""
    match = db.query(Match).filter(Match.id == id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.get("/{id}/odds/history", response_model=List[schemas.OddsResponse])
def get_odds_history(id: str, db: Session = Depends(get_db)):
    """
    Get the full odds history for a match.
    Shows how odds moved over time across all bookmakers.
    """
    return (
        db.query(Odds)
        .filter(Odds.match_id == id)
        .order_by(Odds.fetched_at)
        .all()
    )
