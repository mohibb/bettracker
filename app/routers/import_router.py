from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.models import (
    League, Match, Bookmaker, Odds,
    Bet, BetLeg, BetType, BetStatus, MatchStatus, MatchResult, Selection
)

router = APIRouter(prefix="/import", tags=["Import"])


# ── Request schemas ──

class ImportMatchRequest(BaseModel):
    match_id: str
    league_name: str
    league_key: str
    country: str
    home_team: str
    away_team: str
    kick_off: str                       # ISO datetime string
    status: str = "upcoming"            # "upcoming" | "finished"
    result: Optional[str] = None        # "home" | "draw" | "away" | None
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None
    home_odds: Optional[float] = None   # odds from the sheet (column "1")
    draw_odds: Optional[float] = None   # odds from the sheet (column "x")
    away_odds: Optional[float] = None   # odds from the sheet (column "2")


class ImportBetLeg(BaseModel):
    match_id: str
    selection: str          # "home" | "draw" | "away"
    odds: float             # individual leg odds from the matches sheet


class ImportBetRequest(BaseModel):
    type: str               # "single" | "double" | "triple" | "arbitrage"
    stake: float
    potential_return: float
    placed_at: str          # ISO datetime string
    legs: List[ImportBetLeg]


# ── Helpers ──

def get_or_create_league(db: Session, name: str, key: str, country: str) -> League:
    league = db.query(League).filter(League.key == key).first()
    if not league:
        league = League(name=name, key=key, country=country)
        db.add(league)
        db.commit()
        db.refresh(league)
    return league


def get_or_create_import_bookmaker(db: Session) -> Bookmaker:
    """Returns a special 'Imported' bookmaker for odds that came from a sheet."""
    bm = db.query(Bookmaker).filter(Bookmaker.name == "Imported").first()
    if not bm:
        bm = Bookmaker(name="Imported", api_key=None, is_active=False)
        db.add(bm)
        db.commit()
        db.refresh(bm)
    return bm


def parse_status(s: str) -> MatchStatus:
    try:
        return MatchStatus(s)
    except Exception:
        return MatchStatus.upcoming


def parse_result(s: Optional[str]) -> Optional[MatchResult]:
    if not s:
        return None
    try:
        return MatchResult(s)
    except Exception:
        return None


def parse_bet_type(s: str) -> BetType:
    mapping = {
        "single": BetType.single,
        "double": BetType.double,
        "triple": BetType.triple,
        "arbitrage": BetType.arbitrage,
    }
    return mapping.get(s.lower(), BetType.single)


def parse_selection(s: str) -> Selection:
    mapping = { "home": Selection.home, "draw": Selection.draw, "away": Selection.away }
    return mapping.get(s.lower(), Selection.home)


# ── Endpoints ──

@router.post("/match")
def import_match(data: ImportMatchRequest, db: Session = Depends(get_db)):
    """
    Upsert a single match from an imported sheet row.
    Creates the league if it doesn't exist.
    Creates odds records if home/draw/away odds are provided.
    """
    league = get_or_create_league(db, data.league_name, data.league_key, data.country)

    # Parse kick_off
    try:
        kick_off = datetime.fromisoformat(data.kick_off.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid kick_off date: {data.kick_off}")

    # Upsert match
    match = db.query(Match).filter(Match.id == data.match_id).first()
    if not match:
        match = Match(
            id=data.match_id,
            league_id=league.id,
            home_team=data.home_team,
            away_team=data.away_team,
            kick_off=kick_off,
            status=parse_status(data.status),
            result=parse_result(data.result),
            home_goals=data.home_goals,
            away_goals=data.away_goals,
        )
        db.add(match)
    else:
        # Update mutable fields
        match.home_goals = data.home_goals
        match.away_goals = data.away_goals
        match.result = parse_result(data.result)
        match.status = parse_status(data.status)

    db.commit()

    # Store odds if provided
    if data.home_odds and data.draw_odds and data.away_odds:
        bm = get_or_create_import_bookmaker(db)
        db.add(Odds(
            match_id=match.id,
            bookmaker_id=bm.id,
            home=data.home_odds,
            draw=data.draw_odds,
            away=data.away_odds,
        ))
        db.commit()

    return { "match_id": match.id, "status": "imported" }


@router.post("/bet")
def import_bet(data: ImportBetRequest, db: Session = Depends(get_db)):
    """
    Import a single bet with its legs from a sheet row.
    Determines final status by checking each leg's match result.
    """
    # Parse placed_at
    try:
        placed_at = datetime.fromisoformat(data.placed_at.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid placed_at date: {data.placed_at}")

    bet_type = parse_bet_type(data.type)

    # Build legs and determine bet status
    legs = []
    leg_results = []

    for leg_data in data.legs:
        match = db.query(Match).filter(Match.id == leg_data.match_id).first()
        if not match:
            raise HTTPException(
                status_code=404,
                detail=f"Match {leg_data.match_id} not found — import matches first"
            )

        selection = parse_selection(leg_data.selection)

        # Determine leg result from match result
        if match.result is None:
            leg_result = BetStatus.pending
        elif match.result.value == selection.value:
            leg_result = BetStatus.won
        else:
            leg_result = BetStatus.lost

        if match.status == MatchStatus.cancelled:
            leg_result = BetStatus.void

        leg_results.append(leg_result)
        legs.append(BetLeg(
            match_id=match.id,
            bookmaker_id=None,
            selection=selection,
            odds=leg_data.odds,
            result=leg_result,
        ))

    # Determine overall bet status
    if all(r == BetStatus.pending for r in leg_results):
        bet_status = BetStatus.pending
        actual_return = None
        settled_at = None
    elif any(r == BetStatus.void for r in leg_results):
        bet_status = BetStatus.void
        actual_return = data.stake
        settled_at = placed_at
    elif all(r == BetStatus.won for r in leg_results):
        bet_status = BetStatus.won
        actual_return = data.potential_return
        settled_at = placed_at
    else:
        bet_status = BetStatus.lost
        actual_return = 0.0
        settled_at = placed_at

    bet = Bet(
        type=bet_type,
        stake=data.stake,
        potential_return=data.potential_return,
        actual_return=actual_return,
        status=bet_status,
        placed_at=placed_at,
        settled_at=settled_at,
        legs=legs,
    )
    db.add(bet)
    db.commit()
    db.refresh(bet)

    return { "bet_id": bet.id, "status": bet_status.value, "legs": len(legs) }