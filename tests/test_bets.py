from factories import (
    make_league, make_match, make_bookmaker, make_odds,
    make_bet, make_bet_leg, TestingSessionLocal
)
from app.models import BetStatus, BetType, Selection


class TestPlaceBet:
    def _seed_match_and_odds(self, db):
        league = make_league(db)
        match = make_match(db, league.id)
        bm = make_bookmaker(db)
        make_odds(db, match.id, bm.id)
        return match.id, bm.id

    def test_place_bet_empty_cart_returns_400(self, client):
        r = client.post("/bets/", json={"stake": 10.0})
        assert r.status_code == 400
        assert "empty" in r.json()["detail"].lower()

    def test_place_single_bet(self, client):
        db = TestingSessionLocal()
        match_id, bm_id = self._seed_match_and_odds(db)
        db.close()

        client.post("/cart/legs", json={
            "match_id": match_id,
            "bookmaker_id": bm_id,
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
        match_id, bm_id = self._seed_match_and_odds(db)
        db.close()

        client.post("/cart/legs", json={
            "match_id": match_id, "bookmaker_id": bm_id, "selection": "home"
        })
        client.post("/bets/", json={"stake": 10.0})

        r = client.get("/cart/")
        assert r.json()["legs"] == []


class TestGetBets:
    def test_empty_bets(self, client):
        r = client.get("/bets/")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_bets(self, client):
        db = TestingSessionLocal()
        make_bet(db)
        db.close()

        r = client.get("/bets/")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_filter_by_status(self, client):
        db = TestingSessionLocal()
        make_bet(db, status=BetStatus.pending)
        make_bet(db, status=BetStatus.won)
        db.close()

        r = client.get("/bets/?status=pending")
        assert r.status_code == 200
        assert all(b["status"] == "pending" for b in r.json())


class TestPnL:
    def test_pnl_summary_empty(self, client):
        r = client.get("/bets/summary")
        assert r.status_code == 200

    def test_pnl_reflects_won_bet(self, client):
        db = TestingSessionLocal()
        make_bet(db, status=BetStatus.won, stake=10.0, potential_return=20.0)
        db.close()

        r = client.get("/bets/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["profit"] == 10.0


class TestSettleBet:
    def test_settle_bet_won(self):
        from app.dependencies import settle_bet
        db = TestingSessionLocal()
        league = make_league(db)
        bm = make_bookmaker(db)
        match = make_match(db, league.id)
        bet = make_bet(db, stake=10.0, potential_return=20.0)
        make_bet_leg(db, bet.id, match.id, bm.id, result=BetStatus.won)

        settle_bet(bet, db)

        assert bet.status == BetStatus.won
        assert bet.actual_return == 20.0
        db.close()

    def test_settle_bet_lost(self):
        from app.dependencies import settle_bet
        db = TestingSessionLocal()
        league = make_league(db)
        bm = make_bookmaker(db)
        match = make_match(db, league.id)
        bet = make_bet(db, stake=10.0, potential_return=20.0)
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
        assert bet.actual_return == 10.0
        db.close()
