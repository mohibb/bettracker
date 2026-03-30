from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Bookmaker, ApiKey
from app import schemas

router = APIRouter(prefix="/config", tags=["Config"])


@router.get("/bookmakers", response_model=List[schemas.BookmakerResponse])
def get_bookmakers(db: Session = Depends(get_db)):
    """List all bookmakers."""
    return db.query(Bookmaker).all()


@router.post("/bookmakers", response_model=schemas.BookmakerResponse)
def add_bookmaker(name: str, api_key: str = None, db: Session = Depends(get_db)):
    """
    Add a new bookmaker.
    - name: display name e.g. "Unibet"
    - api_key: the key used by the-odds-api.com e.g. "unibet"
    """
    bookmaker = Bookmaker(name=name, api_key=api_key)
    db.add(bookmaker)
    db.commit()
    db.refresh(bookmaker)
    return bookmaker


@router.patch("/bookmakers/{id}", response_model=schemas.BookmakerResponse)
def toggle_bookmaker(id: int, is_active: bool, db: Session = Depends(get_db)):
    """Enable or disable a bookmaker."""
    bookmaker = db.query(Bookmaker).filter(Bookmaker.id == id).first()
    if not bookmaker:
        raise HTTPException(status_code=404, detail="Bookmaker not found")
    bookmaker.is_active = is_active
    db.commit()
    db.refresh(bookmaker)
    return bookmaker


@router.get("/api-keys/status", response_model=List[schemas.ApiKeyResponse])
def get_api_key_status(db: Session = Depends(get_db)):
    """Check usage and remaining requests for all API keys."""
    keys = db.query(ApiKey).all()
    return [
        {**key.__dict__, "requests_remaining": key.requests_limit - key.requests_used}
        for key in keys
    ]


@router.post("/api-keys", response_model=schemas.ApiKeyResponse)
def add_api_key(data: schemas.ApiKeyAdd, db: Session = Depends(get_db)):
    """Add a new odds API key to the rotation."""
    key = ApiKey(key=data.key, requests_limit=data.requests_limit)
    db.add(key)
    db.commit()
    db.refresh(key)
    return {**key.__dict__, "requests_remaining": key.requests_limit - key.requests_used}
