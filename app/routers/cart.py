from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime
from app import schemas

router = APIRouter(prefix="/cart", tags=["Cart"])

# In-memory cart — simple, no database table needed for a personal project.
# Resets if the server restarts, which is acceptable behaviour.
_cart: List[dict] = []
_cart_created_at: Optional[datetime] = None


def get_cart_contents() -> List[dict]:
    """Returns the current cart contents. Used by the bets router."""
    return _cart


@router.get("/", response_model=schemas.CartResponse)
def get_cart():
    """View current cart contents and inferred bet type."""
    types = {0: "empty", 1: "single", 2: "double", 3: "triple"}
    return {
        "id": 1,
        "legs": _cart,
        "bet_type": types.get(len(_cart), "empty"),
        "created_at": _cart_created_at or datetime.utcnow()
    }


@router.post("/legs")
def add_to_cart(leg: schemas.CartLegAdd):
    """
    Add a match selection to the cart.
    Maximum 3 legs (singles, doubles, triples).
    The same match cannot be added twice.
    """
    global _cart_created_at

    if len(_cart) >= 3:
        raise HTTPException(
            status_code=400,
            detail="Cart is full — maximum 3 matches (single, double, triple)"
        )
    if any(l["match_id"] == leg.match_id for l in _cart):
        raise HTTPException(status_code=400, detail="Match already in cart")

    if not _cart:
        _cart_created_at = datetime.utcnow()

    _cart.append({
        "id": len(_cart) + 1,
        "match_id": leg.match_id,
        "bookmaker_id": leg.bookmaker_id,
        "selection": leg.selection
    })
    return {"message": "Added to cart", "cart_size": len(_cart)}


@router.delete("/legs/{leg_id}")
def remove_from_cart(leg_id: int):
    """Remove a single leg from the cart by its ID."""
    global _cart
    _cart = [l for l in _cart if l["id"] != leg_id]
    return {"message": "Removed from cart", "cart_size": len(_cart)}


@router.delete("/")
def empty_cart():
    """Clear the entire cart."""
    global _cart_created_at
    _cart.clear()
    _cart_created_at = None
    return {"message": "Cart emptied"}
