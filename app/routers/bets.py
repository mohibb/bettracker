from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models import (
    Match, Odds, Bet, BetLeg,
    ArbitrageOpportunity, Notification,
    BetType, BetStatus, MatchStatus, Selection
)
from app import schemas
from app.dependencies import calculate_potential_return, settle_bet
from app.routers.cart import get_cart_contents, empty_cart

router = APIRouter(prefix="/bets", tags=["Bets"])


@router.post("/", response_model=schemas.BetResponse)
def place_bet(data: schemas.PlaceBetRequest, db: Session = Depends(get_db)):
    """
    Place a single, double or triple from whatever is currently in the cart.
    The bet type is inferred automatically from the number of legs in the cart.
    Clears the cart after placing.
    """
    cart = get_cart_contents()
    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty")

    types = {1: BetType.single, 2: BetType.double, 3: BetType.triple}
    bet_type = types[len(cart)]

    legs = []
    all_odds = []

    for item in cart:
        match = db.query(Match).filter(Match.id == item["match_id"]).first()
        if not match:
            raise HTTPException(
                status_code=404,
                detail=f"Match {item['match_id']} not found"
            )
        if match.status != MatchStatus.upcoming:
            raise HTTPException(
                status_code=400,
                detail=f"{match.home_team} vs {match.away_team} is not an upcoming match"
            )

        latest_odds = (
            db.query(Odds)
            .filter(
                Odds.match_id == item["match_id"],
                Odds.bookmaker_id == item["bookmaker_id"]
            )
            .order_by(Odds.fetched_at.desc())
            .first()
        )
        if not latest_odds:
            raise HTTPException(
                status_code=404,
                detail=f"No odds found for match {item['match_id']}"
            )

        selection_odds = getattr(latest_odds, item["selection"].value)
        all_odds.append(selection_odds)
        legs.append(BetLeg(
            match_id=item["match_id"],
            bookmaker_id=item["bookmaker_id"],
            selection=item["selection"],
            odds=selection_odds,
            result=BetStatus.pending
        ))

    bet = Bet(
        type=bet_type,
        stake=data.stake,
        potential_return=calculate_potential_return(all_odds, data.stake),
        status=BetStatus.pending,
        placed_at=datetime.utcnow(),
        legs=legs
    )
    db.add(bet)
    db.commit()
    db.refresh(bet)

    # Clear the cart after a successful bet
    get_cart_contents().clear()
    return bet


@router.post("/arbitrage/{opportunity_id}", response_model=List[schemas.BetResponse])
def place_arbitrage_bet(
    opportunity_id: int,
    data: schemas.PlaceArbitrageBetRequest,
    db: Session = Depends(get_db)
):
    """
    Place an arbitrage bet in one tap.
    Automatically calculates and splits the stake across home, draw and away
    so that the return is identical regardless of the match result.
    Creates three separate bet records, one per outcome.
    """
    opportunity = db.query(ArbitrageOpportunity).filter(
        ArbitrageOpportunity.id == opportunity_id
    ).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    # Calculate the proportional stake for each outcome
    total = (
        (1 / opportunity.home_odds) +
        (1 / opportunity.draw_odds) +
        (1 / opportunity.away_odds)
    )
    target_return = data.stake / total

    bets = []
    for selection, odds, bm_id in [
        (Selection.home, opportunity.home_odds, opportunity.home_bookmaker_id),
        (Selection.draw, opportunity.draw_odds, opportunity.draw_bookmaker_id),
        (Selection.away, opportunity.away_odds, opportunity.away_bookmaker_id),
    ]:
        stake = round(target_return / odds, 2)
        leg = BetLeg(
            match_id=opportunity.match_id,
            bookmaker_id=bm_id,
            selection=selection,
            odds=odds,
            result=BetStatus.pending
        )
        bet = Bet(
            type=BetType.arbitrage,
            stake=stake,
            potential_return=round(odds * stake, 2),
            status=BetStatus.pending,
            placed_at=datetime.utcnow(),
            legs=[leg]
        )
        db.add(bet)
        bets.append(bet)

    db.commit()
    for bet in bets:
        db.refresh(bet)
    return bets


# NOTE: /summary must be defined before /{id} so FastAPI does not try to
# match the string "summary" as a bet ID.
@router.get("/summary", response_model=schemas.BettingSummary)
def get_summary(db: Session = Depends(get_db)):
    """
    Full P&L summary across all settled bets.
    Includes breakdowns by bet type, league and bookmaker.
    """
    settled = db.query(Bet).filter(
        Bet.status.in_([BetStatus.won, BetStatus.lost])
    ).all()
    open_bets = db.query(Bet).filter(Bet.status == BetStatus.pending).count()

    def summarise(bets):
        if not bets:
            return {"bets": 0, "won": 0, "lost": 0, "staked": 0,
                    "returned": 0, "profit": 0, "roi_percent": 0}
        staked = sum(b.stake for b in bets)
        returned = sum(b.actual_return or 0 for b in bets)
        profit = returned - staked
        won = sum(1 for b in bets if b.status == BetStatus.won)
        return {
            "bets": len(bets),
            "won": won,
            "lost": len(bets) - won,
            "staked": round(staked, 2),
            "returned": round(returned, 2),
            "profit": round(profit, 2),
            "roi_percent": round((profit / staked * 100) if staked else 0, 2)
        }

    # Break down by bet type
    by_type = {
        bet_type.value: summarise([b for b in settled if b.type == bet_type])
        for bet_type in BetType
        if any(b.type == bet_type for b in settled)
    }

    # Break down by league and bookmaker
    by_league: dict = {}
    by_bookmaker: dict = {}
    for bet in settled:
        for leg in bet.legs:
            league_name = leg.match.league.name
            by_league.setdefault(league_name, []).append(bet)
            if leg.bookmaker:
                by_bookmaker.setdefault(leg.bookmaker.name, []).append(bet)

    overall = summarise(settled)
    win_rate = round(
        (overall["won"] / overall["bets"] * 100) if overall["bets"] else 0, 2
    )

    return {
        **overall,
        "win_rate_percent": win_rate,
        "open_bets": open_bets,
        "by_type": by_type,
        "by_league": {k: summarise(v) for k, v in by_league.items()},
        "by_bookmaker": {k: summarise(v) for k, v in by_bookmaker.items()}
    }


@router.get("/", response_model=List[schemas.BetResponse])
def get_bets(
    type: Optional[BetType] = None,
    status: Optional[BetStatus] = None,
    db: Session = Depends(get_db)
):
    """
    List all bets, most recent first.
    Optionally filter by type (single/double/triple/arbitrage) or status.
    """
    query = db.query(Bet)
    if type:
        query = query.filter(Bet.type == type)
    if status:
        query = query.filter(Bet.status == status)
    return query.order_by(Bet.placed_at.desc()).all()


@router.get("/{id}", response_model=schemas.BetResponse)
def get_bet(id: int, db: Session = Depends(get_db)):
    """Get a single bet by ID, including all its legs."""
    bet = db.query(Bet).filter(Bet.id == id).first()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    return bet
