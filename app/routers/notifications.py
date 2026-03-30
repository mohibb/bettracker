from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Notification
from app import schemas

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=List[schemas.NotificationResponse])
def get_notifications(db: Session = Depends(get_db)):
    """Get all unread notifications, most recent first."""
    return (
        db.query(Notification)
        .filter(Notification.is_read == False)
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.patch("/{id}/read")
def mark_as_read(id: int, db: Session = Depends(get_db)):
    """Mark a single notification as read."""
    notification = db.query(Notification).filter(Notification.id == id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    return {"message": "Marked as read"}


@router.delete("/")
def clear_notifications(db: Session = Depends(get_db)):
    """Delete all notifications that have already been read."""
    db.query(Notification).filter(Notification.is_read == True).delete()
    db.commit()
    return {"message": "Read notifications cleared"}
