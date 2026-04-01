from factories import TestingSessionLocal
from app.models import Notification


class TestNotifications:
    def test_get_notifications_empty(self, client):
        r = client.get("/notifications/")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_unread_notifications(self, client):
        db = TestingSessionLocal()
        db.add(Notification(message="Arb found!", type="arbitrage", is_read=False))
        db.add(Notification(message="Old news",  type="arbitrage", is_read=True))
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
        n_id = n.id
        db.close()

        r = client.patch(f"/notifications/{n_id}/read")
        assert r.status_code == 200

        r = client.get("/notifications/")
        assert r.json() == []

    def test_clear_read_notifications(self, client):
        db = TestingSessionLocal()
        db.add(Notification(message="Read one", type="arbitrage", is_read=True))
        db.add(Notification(message="Unread",   type="arbitrage", is_read=False))
        db.commit()
        db.close()

        r = client.delete("/notifications/")
        assert r.status_code == 200

        r = client.get("/notifications/")
        assert len(r.json()) == 1
        assert r.json()[0]["message"] == "Unread"
