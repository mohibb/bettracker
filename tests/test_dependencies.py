import pytest
from fastapi import HTTPException
from factories import make_league, make_match, make_bookmaker, make_bet, make_bet_leg, make_api_key, TestingSessionLocal
from app.models import BetStatus, Selection
from app.dependencies import settle_bet, get_active_api_key, use_api_key, detect_arbitrage, calculate_potential_return


class TestGetActiveApiKey:
    def test_raises_503_when_no_keys(self):
        db = TestingSessionLocal()
        with pytest.raises(HTTPException) as exc_info:
            get_active_api_key(db)
        assert exc_info.value.status_code == 503
        db.close()

    def test_raises_503_when_all_keys_exhausted(self):
        db = TestingSessionLocal()
        make_api_key(db, key="full_key", limit=500, used=500)
        with pytest.raises(HTTPException):
            get_active_api_key(db)
        db.close()

    def test_returns_key_with_quota_remaining(self):
        db = TestingSessionLocal()
        make_api_key(db, key="good_key", limit=500, used=100)
        key = get_active_api_key(db)
        assert key.key == "good_key"
        db.close()


class TestUseApiKey:
    def test_increments_requests_used(self):
        db = TestingSessionLocal()
        key = make_api_key(db, used=0)
        use_api_key(key, db)
        assert key.requests_used == 1
        db.close()


class TestDetectArbitrage:
    def test_returns_margin_when_profitable(self):
        margin = detect_arbitrage(1.9, 3.4, 6.0)
        assert margin is not None
        assert margin > 0

    def test_returns_none_when_not_profitable(self):
        margin = detect_arbitrage(1.5, 3.0, 2.5)
        assert margin is None


class TestCalculatePotentialReturn:
    def test_single(self):
        assert calculate_potential_return([2.0], 10.0) == 20.0

    def test_double(self):
        assert calculate_potential_return([2.0, 3.0], 10.0) == 60.0

    def test_triple(self):
        assert calculate_potential_return([2.0, 3.0, 1.5], 10.0) == 90.0
