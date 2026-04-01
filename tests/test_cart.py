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
        for match_id, expected in [("m1", "single"), ("m2", "double"), ("m3", "triple")]:
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
