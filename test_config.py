from conftest import make_league, make_match, make_bookmaker, TestingSessionLocal
from app.models import ArbitrageOpportunity


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
