from unittest.mock import patch, MagicMock
from conftest import (
    make_league, make_match, make_bookmaker, make_odds,
    make_api_key, make_bet, make_bet_leg, TestingSessionLocal
)
from app.models import MatchStatus, MatchResult, Selection


class TestResults:
    def test_get_result_for_finished_match(self, client):
        db = TestingSessionLocal()
        league = make_league(db)
        match = make_match(db, league.id, status=MatchStatus.finished)
        match.home_goals = 2
        match.away_goals = 1
        match.result = MatchResult.home
        match_id = match.id
        db.commit()
        db.close()

        r = client.get(f"/results/{match_id}")
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
