from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import League
from app import schemas

router = APIRouter(prefix="/leagues", tags=["Leagues"])


@router.get("/", response_model=List[schemas.LeagueResponse])
def get_leagues(db: Session = Depends(get_db)):
    """List all leagues."""
    return db.query(League).order_by(League.country, League.name).all()


@router.get("/{id}", response_model=schemas.LeagueResponse)
def get_league(id: int, db: Session = Depends(get_db)):
    """Get a single league by ID."""
    league = db.query(League).filter(League.id == id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return league


@router.post("/", response_model=schemas.LeagueResponse)
def add_league(data: schemas.LeagueBase, db: Session = Depends(get_db)):
    """
    Add a new league.
    - name: display name e.g. "Premier League"
    - key: the sport key used by the-odds-api.com e.g. "soccer_epl"
    - country: e.g. "England"
    """
    existing = db.query(League).filter(League.key == data.key).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"League with key '{data.key}' already exists"
        )
    league = League(name=data.name, key=data.key, country=data.country)
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


@router.delete("/{id}")
def delete_league(id: int, db: Session = Depends(get_db)):
    """Delete a league by ID."""
    league = db.query(League).filter(League.id == id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    db.delete(league)
    db.commit()
    return {"message": f"League '{league.name}' deleted"}
