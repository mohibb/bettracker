from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
from app.models import BetType, BetStatus, MatchStatus, MatchResult, Selection


# --- League ---

class LeagueBase(BaseModel):
    name: str
    key: str
    country: str

class LeagueResponse(LeagueBase):
    id: int

    class Config:
        from_attributes = True


# --- Bookmaker ---

class BookmakerBase(BaseModel):
    name: str
    api_key: Optional[str] = None
    is_active: bool = True

class BookmakerResponse(BookmakerBase):
    id: int

    class Config:
        from_attributes = True


# --- Odds ---

class OddsBase(BaseModel):
    home: float
    draw: float
    away: float

class OddsResponse(OddsBase):
    id: int
    match_id: str
    bookmaker: BookmakerResponse
    fetched_at: datetime

    class Config:
        from_attributes = True


# --- Match ---

class MatchBase(BaseModel):
    home_team: str
    away_team: str
    kick_off: datetime

class MatchResponse(MatchBase):
    id: str
    league: LeagueResponse
    home_goals: Optional[int]
    away_goals: Optional[int]
    result: Optional[MatchResult]
    status: MatchStatus
    odds: List[OddsResponse] = []

    class Config:
        from_attributes = True


# --- Arbitrage ---

class ArbitrageResponse(BaseModel):
    id: int
    match: MatchResponse
    home_odds: float
    draw_odds: float
    away_odds: float
    home_bookmaker: Optional[BookmakerResponse]
    draw_bookmaker: Optional[BookmakerResponse]
    away_bookmaker: Optional[BookmakerResponse]
    margin_percent: float
    detected_at: datetime

    class Config:
        from_attributes = True


# --- Cart ---

class CartLegAdd(BaseModel):
    match_id: str
    bookmaker_id: int
    selection: Selection

class CartLegResponse(BaseModel):
    id: int
    match_id: str
    bookmaker_id: int
    selection: Selection

    class Config:
        from_attributes = True

class CartResponse(BaseModel):
    id: int
    legs: List[CartLegResponse]
    bet_type: str                   # "empty", "single", "double" or "triple"
    created_at: datetime

    class Config:
        from_attributes = True


# --- Bets ---

class BetLegResponse(BaseModel):
    id: int
    match: MatchResponse
    bookmaker: Optional[BookmakerResponse]
    selection: Selection
    odds: float
    result: BetStatus

    class Config:
        from_attributes = True

class BetResponse(BaseModel):
    id: int
    type: BetType
    stake: float
    potential_return: float
    actual_return: Optional[float]
    status: BetStatus
    placed_at: datetime
    settled_at: Optional[datetime]
    legs: List[BetLegResponse]

    class Config:
        from_attributes = True

class PlaceBetRequest(BaseModel):
    stake: float

class PlaceArbitrageBetRequest(BaseModel):
    opportunity_id: int
    stake: float


# --- Summary ---

class BetTypeSummary(BaseModel):
    bets: int
    won: int
    lost: int
    staked: float
    returned: float
    profit: float
    roi_percent: float

class BettingSummary(BaseModel):
    total_staked: float
    total_returned: float
    profit: float
    roi_percent: float
    win_rate_percent: float
    open_bets: int
    by_type: Dict[str, BetTypeSummary]
    by_league: Dict[str, BetTypeSummary]
    by_bookmaker: Dict[str, BetTypeSummary]


# --- Notifications ---

class NotificationResponse(BaseModel):
    id: int
    message: str
    type: str                       # "arbitrage", "bet_settled", "api_key_low"
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationSettings(BaseModel):
    arbitrage_min_margin: float = 1.0       # only notify if margin above this %
    api_key_requests_remaining: int = 50    # notify when this many requests left


# --- API Keys ---

class ApiKeyAdd(BaseModel):
    key: str
    requests_limit: int = 500

class ApiKeyResponse(BaseModel):
    id: int
    requests_used: int
    requests_limit: int
    requests_remaining: int
    is_active: bool
    last_used_at: Optional[datetime]

    class Config:
        from_attributes = True
