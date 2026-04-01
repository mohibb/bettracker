from unittest.mock import patch, MagicMock
from conftest import make_league, make_match, make_bookmaker, make_odds, make_api_key, TestingSessionLocal


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

    def test_get_odds_for_match(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        match = make_match(db, league.id)
        bm = make_bookmaker(db)
        make_odds(db, match.id, bm.id)
        match_id = match.id
        db.close()

        r = client.get(f"/odds/{match_id}")
        assert r.status_code == 200
        assert len(r.json()) == 1


class TestFetchOdds:
    def test_fetch_odds_no_api_key_returns_503(self, client):
        r = client.post("/odds/fetch")
        assert r.status_code == 503

    def test_fetch_odds_stores_and_detects_arbitrage(self, client):
        db = TestingSessionLocal()
        make_api_key(db)
        make_league(db)
        make_bookmaker(db)
        db.close()

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
                    {"name": "Draw",  "price": 3.4},
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
