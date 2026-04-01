from factories import make_bookmaker, make_api_key, TestingSessionLocal


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
