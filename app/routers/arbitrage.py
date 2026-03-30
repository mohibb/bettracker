from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import ArbitrageOpportunity, Match, MatchStatus
from app import schemas

router = APIRouter(prefix="/arbitrage", tags=["Arbitrage"])


@router.get("/", response_model=List[schemas.ArbitrageResponse])
def get_arbitrage_opportunities(db: Session = Depends(get_db)):
    """
    All current live arbitrage opportunities on upcoming matches.
    Sorted by margin — best opportunities first.
    """
    return (
        db.query(ArbitrageOpportunity)
        .join(Match)
        .filter(Match.status == MatchStatus.upcoming)
        .order_by(ArbitrageOpportunity.margin_percent.desc())
        .all()
    )


@router.get("/history", response_model=List[schemas.ArbitrageResponse])
def get_arbitrage_history(db: Session = Depends(get_db)):
    """All past detected arbitrage opportunities, most recent first."""
    return (
        db.query(ArbitrageOpportunity)
        .order_by(ArbitrageOpportunity.detected_at.desc())
        .all()
    )


@router.get("/{id}", response_model=schemas.ArbitrageResponse)
def get_arbitrage_opportunity(id: int, db: Session = Depends(get_db)):
    """Get a single arbitrage opportunity by ID."""
    opportunity = db.query(ArbitrageOpportunity).filter(
        ArbitrageOpportunity.id == id
    ).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opportunity
