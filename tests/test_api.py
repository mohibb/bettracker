"""
BetTracker API — Automated Test Suite
======================================
Run with:
    pytest tests/test_api.py -v

Requires:
    pip install pytest httpx fastapi sqlalchemy

All tests use an in-memory SQLite database so no real PostgreSQL is needed.
The .env DATABASE_URL is overridden via the app's dependency injection system.
"""

import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.main import app
from app.database import Base, get_db
from app.models import (
    League, Match, Bookmaker, Odds, Bet, BetLeg, ArbitrageOpportunity,
    ApiKey, Notification, BetType, BetStatus, MatchStatus, MatchResult, Selection
)

# ---------------------------------------------------------------------------
# Test database setup — SQLite in-memory, isolated per test session
# ---------------------------------------------------------------------------

SQLALCHEMY_TEST_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_db():
    """Drop and recreate all tables before every test for a clean slate."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    # Also reset the in-memory cart between tests
    from app.routers import cart as cart_module
    cart_module._cart.clear()
    cart_module._cart_created_at = None


@pytest.fixture()
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helper factories — create common DB objects concisely
# ---------------------------------------------------------------------------

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


# ===========================================================================
# CONFIG TESTS
# ===========================================================================

class TestGetBookmakers:
    def test_returns_empty_list(self, client):
        r = client.get("/config/bookmakers")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_existing_bookmakers(self, client):
        db = TestingSessionLocal()
        make_bookmaker(db)
        db.close()

        r = client.get("/config/bookmakers")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["name"] == "Unibet"


class TestAddBookmaker:
    def test_add_bookmaker(self, client):
        r = client.post("/config/bookmakers?name=Bet365&api_key=bet365")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Bet365"
        assert body["api_key"] == "bet365"
        assert body["is_active"] is True

    def test_add_bookmaker_without_api_key(self, client):
        r = client.post("/config/bookmakers?name=Manual")
        assert r.status_code == 200
        assert r.json()["api_key"] is None


class TestToggleBookmaker:
    def test_disable_bookmaker(self, client):
        db = TestingSessionLocal()
        bm = make_bookmaker(db)
        bm_id = bm.id
        db.close()

        r = client.patch(f"/config/bookmakers/{bm_id}?is_active=false")
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    def test_enable_bookmaker(self, client):
        db = TestingSessionLocal()
        bm = make_bookmaker(db, is_active=False)
        bm_id = bm.id
        db.close()

        r = client.patch(f"/config/bookmakers/{bm_id}?is_active=true")
        assert r.status_code == 200
        assert r.json()["is_active"] is True

    def test_toggle_nonexistent_bookmaker_returns_404(self, client):
        r = client.patch("/config/bookmakers/999?is_active=false")
        assert r.status_code == 404


class TestApiKeys:
    def test_get_api_key_status_empty(self, client):
        r = client.get("/config/api-keys/status")
        assert r.status_code == 200
        assert r.json() == []

    def test_add_api_key(self, client):
        r = client.post("/config/api-keys", json={"key": "my_key", "requests_limit": 200})
        assert r.status_code == 200
        body = r.json()
        assert body["requests_remaining"] == 200
        assert body["requests_used"] == 0

    def test_requests_remaining_is_calculated(self, client):
        db = TestingSessionLocal()
        make_api_key(db, used=100, limit=500)
        db.close()

        r = client.get("/config/api-keys/status")
        assert r.status_code == 200
        assert r.json()[0]["requests_remaining"] == 400


# ===========================================================================
# MATCHES TESTS
# ===========================================================================

class TestGetMatches:
    def test_empty_list(self, client):
        r = client.get("/matches")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_matches(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        make_match(db, league.id)
        db.close()

        r = client.get("/matches")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_filter_by_status(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        make_match(db, league.id, match_id="m1", status=MatchStatus.upcoming)
        make_match(db, league.id, match_id="m2", status=MatchStatus.finished)
        db.close()

        r = client.get("/matches?status=upcoming")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["id"] == "m1"

    def test_filter_by_league_id(self, client):
        db = TestingSessionLocal()
        l1 = make_league(db, key="epl")
        l2 = make_league(db, name="La Liga", key="la_liga", country="Spain")
        make_match(db, l1.id, match_id="m1")
        make_match(db, l2.id, match_id="m2")
        db.close()

        r = client.get(f"/matches?league_id={l1.id}")
        assert r.status_code == 200
        ids = [m["id"] for m in r.json()]
        assert "m1" in ids
        assert "m2" not in ids


class TestGetMatch:
    def test_get_existing_match(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        make_match(db, league.id)
        db.close()

        r = client.get("/matches/match_abc123")
        assert r.status_code == 200
        assert r.json()["home_team"] == "Arsenal"

    def test_get_nonexistent_match_returns_404(self, client):
        r = client.get("/matches/does_not_exist")
        assert r.status_code == 404


class TestOddsHistory:
    def test_returns_odds_history(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        match = make_match(db, league.id)
        bm = make_bookmaker(db)
        make_odds(db, match.id, bm.id, home=2.0)
        make_odds(db, match.id, bm.id, home=1.9)
        db.close()

        r = client.get(f"/matches/{match.id}/odds/history")
        assert r.status_code == 200
        assert len(r.json()) == 2


# ===========================================================================
# CART TESTS
# ===========================================================================

class TestCart:
    def test_empty_cart(self, client):
        r = client.get("/cart/")
        assert r.status_code == 200
        body = r.json()
        assert body["legs"] == []
        assert body["bet_type"] == "empty"

    def test_add_leg_to_cart(self, client):
        r = client.post("/cart/legs", json={
            "match_id": "m1", "bookmaker_id": 1, "selection": "home"
        })
        assert r.status_code == 200
        assert r.json()["cart_size"] == 1

    def test_bet_type_inferred_correctly(self, client):
        for i, (match_id, expected) in enumerate([
            ("m1", "single"), ("m2", "double"), ("m3", "triple")
        ]):
            client.post("/cart/legs", json={
                "match_id": match_id, "bookmaker_id": 1, "selection": "home"
            })
            r = client.get("/cart/")
            assert r.json()["bet_type"] == expected

    def test_cart_max_3_legs(self, client):
        for match_id in ["m1", "m2", "m3"]:
            client.post("/cart/legs", json={
                "match_id": match_id, "bookmaker_id": 1, "selection": "home"
            })
        r = client.post("/cart/legs", json={
            "match_id": "m4", "bookmaker_id": 1, "selection": "home"
        })
        assert r.status_code == 400
        assert "full" in r.json()["detail"].lower()

    def test_same_match_cannot_be_added_twice(self, client):
        client.post("/cart/legs", json={
            "match_id": "m1", "bookmaker_id": 1, "selection": "home"
        })
        r = client.post("/cart/legs", json={
            "match_id": "m1", "bookmaker_id": 1, "selection": "away"
        })
        assert r.status_code == 400
        assert "already in cart" in r.json()["detail"].lower()

    def test_remove_leg_from_cart(self, client):
        client.post("/cart/legs", json={
            "match_id": "m1", "bookmaker_id": 1, "selection": "home"
        })
        r = client.delete("/cart/legs/1")
        assert r.status_code == 200
        assert r.json()["cart_size"] == 0

    def test_empty_cart_endpoint(self, client):
        client.post("/cart/legs", json={
            "match_id": "m1", "bookmaker_id": 1, "selection": "home"
        })
        r = client.delete("/cart/")
        assert r.status_code == 200
        assert client.get("/cart/").json()["legs"] == []


# ===========================================================================
# ODDS TESTS
# ===========================================================================

class TestGetOdds:
    def test_get_latest_odds_empty(self, client):
        r = client.get("/odds/")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_latest_odds(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        match = make_match(db, league.id)
        bm = make_bookmaker(db)
        make_odds(db, match.id, bm.id)
        db.close()

        r = client.get("/odds/")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_get_match_odds(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        match = make_match(db, league.id)
        bm = make_bookmaker(db)
        make_odds(db, match.id, bm.id, home=2.5)
        db.close()

        r = client.get(f"/odds/{match.id}")
        assert r.status_code == 200
        assert r.json()[0]["home"] == 2.5

    def test_get_odds_unknown_match_returns_empty(self, client):
        r = client.get("/odds/nonexistent_match")
        assert r.status_code == 200
        assert r.json() == []


class TestFetchOdds:
    def test_fetch_odds_no_api_key_returns_503(self, client):
        r = client.post("/odds/fetch")
        assert r.status_code == 503

    def test_fetch_odds_calls_external_api(self, client):
        db = TestingSessionLocal()
        make_api_key(db)
        league = make_league(db)
        bm = make_bookmaker(db)
        db.close()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "ext_match_1",
                "home_team": "Man City",
                "away_team": "Liverpool",
                "commence_time": "2026-06-10T15:00:00Z",
                "bookmakers": [
                    {
                        "key": "unibet",
                        "markets": [{"outcomes": [
                            {"name": "Man City", "price": 1.9},
                            {"name": "Draw", "price": 3.4},
                            {"name": "Liverpool", "price": 4.0},
                        ]}]
                    }
                ]
            }
        ]

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            r = client.post("/odds/fetch")

        assert r.status_code == 200
        body = r.json()
        assert body["new_odds_stored"] == 1

    def test_fetch_odds_creates_arbitrage_opportunity(self, client):
        """Odds where sum of inverse < 1 should create an arbitrage record."""
        db = TestingSessionLocal()
        make_api_key(db)
        league = make_league(db)
        bm = make_bookmaker(db)
        db.close()

        # These odds give sum(1/o) = 0.526 + 0.294 + 0.167 ≈ 0.987 < 1
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{
            "id": "arb_match",
            "home_team": "TeamA",
            "away_team": "TeamB",
            "commence_time": "2026-06-15T15:00:00Z",
            "bookmakers": [{
                "key": "unibet",
                "markets": [{"outcomes": [
                    {"name": "TeamA", "price": 1.9},
                    {"name": "Draw", "price": 3.4},
                    {"name": "TeamB", "price": 6.0},
                ]}]
            }]
        }]

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            r = client.post("/odds/fetch")

        assert r.status_code == 200
        assert r.json()["arbitrage_opportunities_found"] == 1


# ===========================================================================
# ARBITRAGE TESTS
# ===========================================================================

class TestArbitrage:
    def _seed_arb(self, db):
        league = make_league(db)
        match = make_match(db, league.id)
        bm = make_bookmaker(db)
        arb = ArbitrageOpportunity(
            match_id=match.id,
            home_odds=2.1,
            draw_odds=3.5,
            away_odds=4.0,
            home_bookmaker_id=bm.id,
            draw_bookmaker_id=bm.id,
            away_bookmaker_id=bm.id,
            margin_percent=1.23,
        )
        db.add(arb)
        db.commit()
        db.refresh(arb)
        return arb

    def test_get_opportunities_empty(self, client):
        r = client.get("/arbitrage/")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_opportunities_returns_upcoming_only(self, client):
        db = TestingSessionLocal()
        self._seed_arb(db)
        db.close()

        r = client.get("/arbitrage/")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_get_history(self, client):
        db = TestingSessionLocal()
        self._seed_arb(db)
        db.close()

        r = client.get("/arbitrage/history")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_get_single_opportunity(self, client):
        db = TestingSessionLocal()
        arb = self._seed_arb(db)
        arb_id = arb.id
        db.close()

        r = client.get(f"/arbitrage/{arb_id}")
        assert r.status_code == 200
        assert r.json()["margin_percent"] == 1.23

    def test_get_nonexistent_opportunity_returns_404(self, client):
        r = client.get("/arbitrage/9999")
        assert r.status_code == 404


# ===========================================================================
# BETS TESTS
# ===========================================================================

class TestPlaceBet:
    def _seed_match_and_odds(self, db):
        league = make_league(db)
        match = make_match(db, league.id)
        bm = make_bookmaker(db)
        make_odds(db, match.id, bm.id)
        return match, bm

    def test_place_bet_empty_cart_returns_400(self, client):
        r = client.post("/bets/", json={"stake": 10.0})
        assert r.status_code == 400
        assert "empty" in r.json()["detail"].lower()

    def test_place_single_bet(self, client):
        db = TestingSessionLocal()
        match, bm = self._seed_match_and_odds(db)
        db.close()

        client.post("/cart/legs", json={
            "match_id": match.id,
            "bookmaker_id": bm.id,
            "selection": "home"
        })

        r = client.post("/bets/", json={"stake": 10.0})
        assert r.status_code == 200
        body = r.json()
        assert body["type"] == "single"
        assert body["stake"] == 10.0
        assert body["status"] == "pending"
        assert len(body["legs"]) == 1

    def test_cart_cleared_after_bet(self, client):
        db = TestingSessionLocal()
        match, bm = self._seed_match_and_odds(db)
        db.close()

        client.post("/cart/legs", json={
            "match_id": match.id, "bookmaker_id": bm.id, "selection": "home"
        })
        client.post("/bets/", json={"stake": 5.0})

        r = client.get("/cart/")
        assert r.json()["legs"] == []

    def test_place_double_bet(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        bm = make_bookmaker(db)
        m1 = make_match(db, league.id, match_id="m1")
        m2 = make_match(db, league.id, match_id="m2", home="Bayern", away="Dortmund")
        make_odds(db, m1.id, bm.id)
        make_odds(db, m2.id, bm.id)
        db.close()

        client.post("/cart/legs", json={"match_id": "m1", "bookmaker_id": bm.id, "selection": "home"})
        client.post("/cart/legs", json={"match_id": "m2", "bookmaker_id": bm.id, "selection": "away"})

        r = client.post("/bets/", json={"stake": 10.0})
        assert r.status_code == 200
        assert r.json()["type"] == "double"

    def test_bet_on_finished_match_returns_400(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        bm = make_bookmaker(db)
        match = make_match(db, league.id, status=MatchStatus.finished)
        make_odds(db, match.id, bm.id)
        db.close()

        client.post("/cart/legs", json={
            "match_id": match.id, "bookmaker_id": bm.id, "selection": "home"
        })
        r = client.post("/bets/", json={"stake": 10.0})
        assert r.status_code == 400

    def test_potential_return_calculated_correctly(self, client):
        db = TestingSessionLocal()
        match, bm = self._seed_match_and_odds(db)
        db.close()

        client.post("/cart/legs", json={
            "match_id": match.id, "bookmaker_id": bm.id, "selection": "home"
        })
        r = client.post("/bets/", json={"stake": 10.0})
        assert r.status_code == 200
        # Home odds is 2.0, stake is 10 → potential return = 20.0
        assert r.json()["potential_return"] == 20.0


class TestPlaceArbitrageBet:
    def _seed_arb(self, db):
        league = make_league(db)
        match = make_match(db, league.id)
        bm = make_bookmaker(db)
        arb = ArbitrageOpportunity(
            match_id=match.id,
            home_odds=2.1,
            draw_odds=3.5,
            away_odds=4.0,
            home_bookmaker_id=bm.id,
            draw_bookmaker_id=bm.id,
            away_bookmaker_id=bm.id,
            margin_percent=1.23,
        )
        db.add(arb)
        db.commit()
        db.refresh(arb)
        return arb

    def test_place_arbitrage_bet(self, client):
        db = TestingSessionLocal()
        arb = self._seed_arb(db)
        arb_id = arb.id
        db.close()

        r = client.post(f"/bets/arbitrage/{arb_id}", json={
            "opportunity_id": arb_id, "stake": 100.0
        })
        assert r.status_code == 200
        bets = r.json()
        assert len(bets) == 3
        assert all(b["type"] == "arbitrage" for b in bets)

    def test_arbitrage_stakes_sum_to_total(self, client):
        db = TestingSessionLocal()
        arb = self._seed_arb(db)
        arb_id = arb.id
        db.close()

        r = client.post(f"/bets/arbitrage/{arb_id}", json={
            "opportunity_id": arb_id, "stake": 100.0
        })
        bets = r.json()
        total_staked = sum(b["stake"] for b in bets)
        # Stakes should sum close to 100 (within rounding)
        assert abs(total_staked - 100.0) < 0.10

    def test_arbitrage_nonexistent_opportunity_returns_404(self, client):
        r = client.post("/bets/arbitrage/9999", json={
            "opportunity_id": 9999, "stake": 100.0
        })
        assert r.status_code == 404


class TestGetBets:
    def test_get_bets_empty(self, client):
        r = client.get("/bets/")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_bets_filter_by_type(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        bm = make_bookmaker(db)
        match = make_match(db, league.id)

        single = make_bet(db, bet_type=BetType.single)
        make_bet_leg(db, single.id, match.id, bm.id)

        double = make_bet(db, bet_type=BetType.double)
        make_bet_leg(db, double.id, match.id, bm.id)
        db.close()

        r = client.get("/bets/?type=single")
        assert r.status_code == 200
        assert all(b["type"] == "single" for b in r.json())

    def test_get_bets_filter_by_status(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        bm = make_bookmaker(db)
        match = make_match(db, league.id)

        won = make_bet(db, status=BetStatus.won, potential_return=20.0)
        make_bet_leg(db, won.id, match.id, bm.id)

        lost = make_bet(db, status=BetStatus.lost, potential_return=20.0)
        make_bet_leg(db, lost.id, match.id, bm.id)
        db.close()

        r = client.get("/bets/?status=won")
        assert all(b["status"] == "won" for b in r.json())

    def test_get_single_bet(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        bm = make_bookmaker(db)
        match = make_match(db, league.id)
        bet = make_bet(db)
        make_bet_leg(db, bet.id, match.id, bm.id)
        bet_id = bet.id
        db.close()

        r = client.get(f"/bets/{bet_id}")
        assert r.status_code == 200
        assert r.json()["id"] == bet_id

    def test_get_nonexistent_bet_returns_404(self, client):
        r = client.get("/bets/99999")
        assert r.status_code == 404


class TestBettingSummary:
    def test_summary_no_bets(self, client):
        r = client.get("/bets/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["staked"] == 0
        assert body["profit"] == 0
        assert body["open_bets"] == 0

    def test_summary_with_settled_bets(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        bm = make_bookmaker(db)
        match = make_match(db, league.id)

        won = make_bet(db, stake=10.0, status=BetStatus.won, potential_return=20.0)
        make_bet_leg(db, won.id, match.id, bm.id, result=BetStatus.won)

        lost = make_bet(db, stake=10.0, status=BetStatus.lost, potential_return=20.0)
        make_bet_leg(db, lost.id, match.id, bm.id, result=BetStatus.lost)
        db.close()

        r = client.get("/bets/summary")
        body = r.json()
        assert body["bets"] == 2
        assert body["won"] == 1
        assert body["lost"] == 1
        assert body["staked"] == 20.0
        assert body["returned"] == 20.0
        assert body["profit"] == 0.0


# ===========================================================================
# RESULTS TESTS
# ===========================================================================

class TestResults:
    def test_get_result(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        match = make_match(db, league.id, status=MatchStatus.finished)
        match.home_goals = 2
        match.away_goals = 1
        match.result = MatchResult.home
        db.commit()
        db.close()

        r = client.get(f"/results/{match.id}")
        assert r.status_code == 200
        body = r.json()
        assert body["result"] == "home"
        assert body["home_goals"] == 2

    def test_get_result_not_found(self, client):
        r = client.get("/results/nonexistent_match")
        assert r.status_code == 404

    def test_check_results_no_api_key_returns_503(self, client):
        r = client.post("/results/check")
        assert r.status_code == 503

    def test_check_results_settles_pending_legs(self, client):
        db = TestingSessionLocal()
        make_api_key(db)
        league = make_league(db)
        match = make_match(db, league.id)
        bm = make_bookmaker(db)
        make_odds(db, match.id, bm.id)

        bet = make_bet(db)
        make_bet_leg(db, bet.id, match.id, bm.id, selection=Selection.home)
        db.close()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{
            "id": "match_abc123",
            "completed": True,
            "scores": [
                {"name": "Arsenal", "score": "2"},
                {"name": "Chelsea", "score": "1"},
            ]
        }]

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            r = client.post("/results/check")

        assert r.status_code == 200
        assert r.json()["legs_settled"] == 1


# ===========================================================================
# NOTIFICATIONS TESTS
# ===========================================================================

class TestNotifications:
    def test_get_notifications_empty(self, client):
        r = client.get("/notifications/")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_unread_notifications(self, client):
        db = TestingSessionLocal()
        db.add(Notification(message="Arb found!", type="arbitrage", is_read=False))
        db.add(Notification(message="Old news", type="arbitrage", is_read=True))
        db.commit()
        db.close()

        r = client.get("/notifications/")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["message"] == "Arb found!"

    def test_mark_notification_as_read(self, client):
        db = TestingSessionLocal()
        n = Notification(message="Test", type="arbitrage", is_read=False)
        db.add(n)
        db.commit()
        db.refresh(n)
        n_id = n.id
        db.close()

        r = client.patch(f"/notifications/{n_id}/read")
        assert r.status_code == 200

        r2 = client.get("/notifications/")
        assert len(r2.json()) == 0  # now read, so filtered out

    def test_mark_nonexistent_notification_returns_404(self, client):
        r = client.patch("/notifications/9999/read")
        assert r.status_code == 404

    def test_clear_read_notifications(self, client):
        db = TestingSessionLocal()
        db.add(Notification(message="Read one", type="arbitrage", is_read=True))
        db.add(Notification(message="Unread", type="arbitrage", is_read=False))
        db.commit()
        db.close()

        r = client.delete("/notifications/")
        assert r.status_code == 200

        # Unread notification should remain
        db2 = TestingSessionLocal()
        remaining = db2.query(Notification).all()
        db2.close()
        assert len(remaining) == 1
        assert remaining[0].is_read is False


# ===========================================================================
# DEPENDENCY UNIT TESTS
# ===========================================================================

class TestDependencies:
    def test_detect_arbitrage_returns_margin_when_profitable(self):
        from app.dependencies import detect_arbitrage
        # 1/1.9 + 1/3.4 + 1/6.0 ≈ 0.987 < 1
        margin = detect_arbitrage(1.9, 3.4, 6.0)
        assert margin is not None
        assert margin > 0

    def test_detect_arbitrage_returns_none_when_not_profitable(self):
        from app.dependencies import detect_arbitrage
        margin = detect_arbitrage(1.5, 3.0, 2.5)
        assert margin is None

    def test_calculate_potential_return_single(self):
        from app.dependencies import calculate_potential_return
        assert calculate_potential_return([2.0], 10.0) == 20.0

    def test_calculate_potential_return_double(self):
        from app.dependencies import calculate_potential_return
        assert calculate_potential_return([2.0, 3.0], 10.0) == 60.0

    def test_calculate_potential_return_triple(self):
        from app.dependencies import calculate_potential_return
        result = calculate_potential_return([2.0, 3.0, 1.5], 10.0)
        assert result == 90.0

    def test_settle_bet_won(self):
        from app.dependencies import settle_bet
        db = TestingSessionLocal()
        league = make_league(db)
        bm = make_bookmaker(db)
        match = make_match(db, league.id)
        bet = make_bet(db, potential_return=30.0)
        leg = make_bet_leg(db, bet.id, match.id, bm.id, result=BetStatus.won)

        settle_bet(bet, db)

        assert bet.status == BetStatus.won
        assert bet.actual_return == 30.0
        db.close()

    def test_settle_bet_lost(self):
        from app.dependencies import settle_bet
        db = TestingSessionLocal()
        league = make_league(db)
        bm = make_bookmaker(db)
        match = make_match(db, league.id)
        bet = make_bet(db, potential_return=30.0)
        make_bet_leg(db, bet.id, match.id, bm.id, result=BetStatus.lost)

        settle_bet(bet, db)

        assert bet.status == BetStatus.lost
        assert bet.actual_return == 0.0
        db.close()

    def test_settle_bet_void_if_any_leg_void(self):
        from app.dependencies import settle_bet
        db = TestingSessionLocal()
        league = make_league(db)
        bm = make_bookmaker(db)
        m1 = make_match(db, league.id, match_id="m1")
        m2 = make_match(db, league.id, match_id="m2", home="X", away="Y")
        bet = make_bet(db, stake=10.0, potential_return=40.0)
        make_bet_leg(db, bet.id, m1.id, bm.id, result=BetStatus.won)
        make_bet_leg(db, bet.id, m2.id, bm.id, result=BetStatus.void)

        settle_bet(bet, db)

        assert bet.status == BetStatus.void
        assert bet.actual_return == 10.0  # stake returned
        db.close()

    def test_get_active_api_key_raises_when_none(self):
        from app.dependencies import get_active_api_key
        from fastapi import HTTPException
        db = TestingSessionLocal()
        with pytest.raises(HTTPException) as exc_info:
            get_active_api_key(db)
        assert exc_info.value.status_code == 503
        db.close()

    def test_get_active_api_key_skips_exhausted_keys(self):
        from app.dependencies import get_active_api_key
        from fastapi import HTTPException
        db = TestingSessionLocal()
        make_api_key(db, key="full_key", limit=500, used=500)
        with pytest.raises(HTTPException):
            get_active_api_key(db)
        db.close()

    def test_use_api_key_increments_count(self):
        from app.dependencies import use_api_key
        db = TestingSessionLocal()
        key = make_api_key(db, used=0)
        use_api_key(key, db)
        assert key.requests_used == 1
        db.close()
