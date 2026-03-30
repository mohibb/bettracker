from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


# --- Enums ---

class MatchStatus(str, enum.Enum):
    upcoming = "upcoming"
    live = "live"
    finished = "finished"
    cancelled = "cancelled"


class MatchResult(str, enum.Enum):
    home = "home"
    draw = "draw"
    away = "away"


class Selection(str, enum.Enum):
    home = "home"
    draw = "draw"
    away = "away"


class BetType(str, enum.Enum):
    single = "single"
    double = "double"
    triple = "triple"
    arbitrage = "arbitrage"


class BetStatus(str, enum.Enum):
    pending = "pending"
    won = "won"
    lost = "lost"
    void = "void"


# --- Tables ---

class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)       # "UEFA Champions League"
    key = Column(String, nullable=False)         # "soccer_uefa_champs_league"
    country = Column(String, nullable=False)     # "Europe"

    matches = relationship("Match", back_populates="league")


class Match(Base):
    __tablename__ = "matches"

    id = Column(String, primary_key=True)        # hex ID from the-odds-api.com
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    kick_off = Column(DateTime, nullable=False)
    home_goals = Column(Integer, nullable=True)
    away_goals = Column(Integer, nullable=True)
    result = Column(Enum(MatchResult), nullable=True)
    status = Column(Enum(MatchStatus), default=MatchStatus.upcoming)

    league = relationship("League", back_populates="matches")
    odds = relationship("Odds", back_populates="match")
    bet_legs = relationship("BetLeg", back_populates="match")
    arbitrage_opportunities = relationship("ArbitrageOpportunity", back_populates="match")


class Bookmaker(Base):
    __tablename__ = "bookmakers"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)        # "Unibet" — display name
    api_key = Column(String, nullable=True)      # "unibet" — key used by the-odds-api.com
    is_active = Column(Boolean, default=True)

    odds = relationship("Odds", back_populates="bookmaker")
    bet_legs = relationship("BetLeg", back_populates="bookmaker")


class Odds(Base):
    __tablename__ = "odds"

    id = Column(Integer, primary_key=True)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False)
    bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False)
    home = Column(Float, nullable=False)
    draw = Column(Float, nullable=False)
    away = Column(Float, nullable=False)
    fetched_at = Column(DateTime, server_default=func.now())

    match = relationship("Match", back_populates="odds")
    bookmaker = relationship("Bookmaker", back_populates="odds")


class ArbitrageOpportunity(Base):
    __tablename__ = "arbitrage_opportunities"

    id = Column(Integer, primary_key=True)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False)
    home_odds = Column(Float, nullable=False)
    draw_odds = Column(Float, nullable=False)
    away_odds = Column(Float, nullable=False)
    home_bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=True)
    draw_bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=True)
    away_bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=True)
    margin_percent = Column(Float, nullable=False)
    detected_at = Column(DateTime, server_default=func.now())

    match = relationship("Match", back_populates="arbitrage_opportunities")
    home_bookmaker = relationship("Bookmaker", foreign_keys=[home_bookmaker_id])
    draw_bookmaker = relationship("Bookmaker", foreign_keys=[draw_bookmaker_id])
    away_bookmaker = relationship("Bookmaker", foreign_keys=[away_bookmaker_id])


class Bet(Base):
    __tablename__ = "bets"

    id = Column(Integer, primary_key=True)
    type = Column(Enum(BetType), nullable=False)
    stake = Column(Float, nullable=False)
    potential_return = Column(Float, nullable=False)
    actual_return = Column(Float, nullable=True)
    status = Column(Enum(BetStatus), default=BetStatus.pending)
    placed_at = Column(DateTime, nullable=False)
    settled_at = Column(DateTime, nullable=True)

    legs = relationship("BetLeg", back_populates="bet")


class BetLeg(Base):
    __tablename__ = "bet_legs"

    id = Column(Integer, primary_key=True)
    bet_id = Column(Integer, ForeignKey("bets.id"), nullable=False)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False)
    bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=True)
    selection = Column(Enum(Selection), nullable=False)
    odds = Column(Float, nullable=False)
    result = Column(Enum(BetStatus), default=BetStatus.pending)

    bet = relationship("Bet", back_populates="legs")
    match = relationship("Match", back_populates="bet_legs")
    bookmaker = relationship("Bookmaker", back_populates="bet_legs")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False)
    requests_used = Column(Integer, default=0)
    requests_limit = Column(Integer, default=500)
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    message = Column(String, nullable=False)
    type = Column(String, nullable=False)        # "arbitrage", "bet_settled", "api_key_low"
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
