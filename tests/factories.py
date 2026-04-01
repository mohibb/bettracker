import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import (
    League, Match, Bookmaker, Odds, Bet, BetLeg,
    ApiKey, BetType, BetStatus, MatchStatus, Selection
)

SQLALCHEMY_TEST_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def make_league(db, name="Premier League", key="soccer_epl", country="UK"):
    league = League(name=name, key=key, country=country)
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


def make_bookmaker(db, name="Unibet", api_key="unibet", is_active=True):
    bm = Bookmaker(name=name, api_key=api_key, is_active=is_active)
    db.add(bm)
    db.commit()
    db.refresh(bm)
    return bm


def make_match(db, league_id, home="Arsenal", away="Chelsea",
               status=MatchStatus.upcoming, match_id=None):
    m = Match(
        id=match_id or "match_abc123",
        league_id=league_id,
        home_team=home,
        away_team=away,
        kick_off=datetime(2026, 6, 1, 15, 0),
        status=status,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def make_odds(db, match_id, bookmaker_id, home=2.0, draw=3.0, away=4.0):
    o = Odds(match_id=match_id, bookmaker_id=bookmaker_id,
             home=home, draw=draw, away=away)
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


def make_api_key(db, key="test_key", limit=500, used=0):
    k = ApiKey(key=key, requests_limit=limit, requests_used=used, is_active=True)
    db.add(k)
    db.commit()
    db.refresh(k)
    return k


def make_bet(db, bet_type=BetType.single, stake=10.0,
             status=BetStatus.pending, potential_return=20.0):
    bet = Bet(
        type=bet_type,
        stake=stake,
        potential_return=potential_return,
        status=status,
        actual_return=potential_return if status == BetStatus.won else
                      0.0 if status == BetStatus.lost else None,
        placed_at=datetime.utcnow(),
    )
    db.add(bet)
    db.commit()
    db.refresh(bet)
    return bet


def make_bet_leg(db, bet_id, match_id, bookmaker_id,
                 selection=Selection.home, odds=2.0,
                 result=BetStatus.pending):
    leg = BetLeg(
        bet_id=bet_id,
        match_id=match_id,
        bookmaker_id=bookmaker_id,
        selection=selection,
        odds=odds,
        result=result,
    )
    db.add(leg)
    db.commit()
    db.refresh(leg)
    return leg
