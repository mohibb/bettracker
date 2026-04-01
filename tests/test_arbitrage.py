from conftest import make_league, make_match, make_bookmaker, make_odds, TestingSessionLocal
from app.models import MatchStatus


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
        l1_id = l1.id
        make_match(db, l1.id, match_id="m1")
        make_match(db, l2.id, match_id="m2")
        db.close()

        r = client.get(f"/matches?league_id={l1_id}")
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
        match_id = match.id
        bm = make_bookmaker(db)
        make_odds(db, match.id, bm.id, home=2.0)
        make_odds(db, match.id, bm.id, home=1.9)
        db.close()

        r = client.get(f"/matches/{match_id}/odds/history")
        assert r.status_code == 200
        assert len(r.json()) == 2
