import pytest
from fastapi.testclient import TestClient
import tempfile
from pathlib import Path


@pytest.fixture
def client(tmp_path):
    import config
    config.DB_PATH = tmp_path / "test.db"
    config.DATA_DIR = tmp_path
    config.IMAGES_DIR = tmp_path / "images"

    from main import app, get_db
    from db import Database

    db = Database(config.DB_PATH)
    db.init()

    def override_get_db():
        return db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestPostLog:
    def test_create_meal_entry(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T08:30:00Z",
            "type": "meal",
            "raw_input": "rice and chicken",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["id"] == 1

    def test_create_flare_entry(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T10:00:00Z",
            "type": "flare",
            "severity": 7,
            "notes": "itchy arms",
        })
        assert resp.status_code == 201

    def test_create_medication_entry(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T09:00:00Z",
            "type": "medication",
            "medication_name": "cetirizine",
            "medication_dose": "10mg",
        })
        assert resp.status_code == 201

    def test_create_note_entry(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T11:00:00Z",
            "type": "note",
            "notes": "ate out at Thai restaurant",
        })
        assert resp.status_code == 201

    def test_invalid_type_rejected(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T08:00:00Z",
            "type": "invalid",
        })
        assert resp.status_code == 422


class TestGetLogs:
    def test_list_all_entries(self, client):
        client.post("/api/log", json={"timestamp": "2026-03-23T08:00:00Z", "type": "meal", "raw_input": "toast"})
        client.post("/api/log", json={"timestamp": "2026-03-23T09:00:00Z", "type": "flare", "severity": 3})
        resp = client.get("/api/logs")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_type(self, client):
        client.post("/api/log", json={"timestamp": "2026-03-23T08:00:00Z", "type": "meal", "raw_input": "toast"})
        client.post("/api/log", json={"timestamp": "2026-03-23T09:00:00Z", "type": "flare", "severity": 3})
        resp = client.get("/api/logs?type=meal")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_date_range(self, client):
        client.post("/api/log", json={"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "toast"})
        client.post("/api/log", json={"timestamp": "2026-03-23T08:00:00Z", "type": "meal", "raw_input": "rice"})
        resp = client.get("/api/logs?from=2026-03-23T00:00:00Z&to=2026-03-23T23:59:59Z")
        assert len(resp.json()) == 1


class TestUpdateDeleteLog:
    def test_update_entry(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T08:00:00Z", "type": "meal", "raw_input": "toast"
        })
        entry_id = resp.json()["id"]
        resp = client.put(f"/api/log/{entry_id}", json={"raw_input": "toast with butter"})
        assert resp.status_code == 200

    def test_delete_entry(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T08:00:00Z", "type": "meal", "raw_input": "toast"
        })
        entry_id = resp.json()["id"]
        resp = client.delete(f"/api/log/{entry_id}")
        assert resp.status_code == 200
        resp = client.get("/api/logs")
        assert len(resp.json()) == 0

    def test_update_nonexistent_returns_404(self, client):
        resp = client.put("/api/log/999", json={"raw_input": "nope"})
        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete("/api/log/999")
        assert resp.status_code == 404


class TestAdminEndpoints:
    def test_list_ingredients(self, client):
        resp = client.get("/api/admin/ingredients")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_add_alias(self, client):
        resp = client.post("/api/admin/aliases", json={
            "variant": "tamari",
            "canonical": "soy sauce",
        })
        assert resp.status_code == 201


class TestPushSubscription:
    def test_subscribe(self, client):
        resp = client.post("/api/push/subscribe", json={
            "endpoint": "https://push.example.com/sub1",
            "keys": {"p256dh": "key1", "auth": "auth1"},
        })
        assert resp.status_code == 201
