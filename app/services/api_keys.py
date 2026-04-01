from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import ApiKey


def get_active_api_key(db: Session) -> ApiKey:
    """
    Get the next available API key with quota remaining.
    Automatically skips exhausted keys.
    Raises 503 if none are available.
    """
    key = db.query(ApiKey).filter(
        ApiKey.is_active == True,
        ApiKey.requests_used < ApiKey.requests_limit
    ).order_by(ApiKey.id).first()

    if not key:
        raise HTTPException(status_code=503, detail="No API keys available")
    return key


def use_api_key(key: ApiKey, db: Session) -> None:
    """Increment usage count on an API key after consuming a request."""
    key.requests_used += 1
    key.last_used_at = datetime.utcnow()
    db.commit()
