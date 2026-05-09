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

    def test_list_aliases(self, client):
        client.post("/api/admin/aliases", json={"variant": "tamari", "canonical": "soy sauce"})
        client.post("/api/admin/aliases", json={"variant": "capsicum", "canonical": "bell pepper"})
        resp = client.get("/api/admin/aliases")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_delete_alias(self, client):
        client.post("/api/admin/aliases", json={"variant": "tamari", "canonical": "soy sauce"})
        resp = client.delete("/api/admin/aliases/tamari")
        assert resp.status_code == 200
        assert client.get("/api/admin/aliases").json() == []

    def test_add_composition(self, client):
        resp = client.post("/api/admin/compositions", json={
            "parent": "Continental Chicken Stock Pot",
            "children": ["yeast extract", "salt", "monosodium glutamate"],
            "source": "manual",
        })
        assert resp.status_code == 201
        listing = client.get("/api/admin/compositions").json()
        assert len(listing) == 1
        assert listing[0]["parent"] == "continental chicken stock pot"
        assert listing[0]["children"] == ["yeast extract", "salt", "monosodium glutamate"]
        assert listing[0]["source"] == "manual"

    def test_replace_composition(self, client):
        client.post("/api/admin/compositions", json={
            "parent": "stock pot", "children": ["yeast extract", "salt"], "source": "manual",
        })
        client.post("/api/admin/compositions", json={
            "parent": "stock pot", "children": ["yeast extract", "salt", "msg"], "source": "manual",
        })
        listing = client.get("/api/admin/compositions").json()
        assert listing[0]["children"] == ["yeast extract", "salt", "msg"]

    def test_delete_composition(self, client):
        client.post("/api/admin/compositions", json={
            "parent": "stock pot", "children": ["yeast extract"], "source": "manual",
        })
        resp = client.delete("/api/admin/compositions/stock pot")
        assert resp.status_code == 200
        assert client.get("/api/admin/compositions").json() == []


class TestPushSubscription:
    def test_subscribe(self, client):
        resp = client.post("/api/push/subscribe", json={
            "endpoint": "https://push.example.com/sub1",
            "keys": {"p256dh": "key1", "auth": "auth1"},
        })
        assert resp.status_code == 201


class TestEnvironmentReadings:
    def _readings(self, n=3):
        return [
            {
                "timestamp": f"2026-04-14T22:{i:02d}:00Z",
                "temperature": 22.0 + i * 0.1,
                "humidity": 55.0 + i * 0.2,
            }
            for i in range(n)
        ]

    def test_post_accepts_batch_and_returns_counts(self, client):
        readings = self._readings(5)
        resp = client.post("/api/environment", json={"readings": readings})
        assert resp.status_code == 201
        data = resp.json()
        assert data == {"inserted": 5, "total": 5}

    def test_post_deduplicates_on_timestamp(self, client):
        readings = self._readings(3)
        first = client.post("/api/environment", json={"readings": readings})
        assert first.json() == {"inserted": 3, "total": 3}
        second = client.post("/api/environment", json={"readings": readings})
        assert second.json() == {"inserted": 0, "total": 3}

    def test_post_partial_overlap(self, client):
        client.post("/api/environment", json={"readings": self._readings(3)})
        overlap_batch = self._readings(5)  # includes the original 3
        resp = client.post("/api/environment", json={"readings": overlap_batch})
        assert resp.json() == {"inserted": 2, "total": 5}

    def test_post_empty_batch(self, client):
        resp = client.post("/api/environment", json={"readings": []})
        assert resp.status_code == 201
        assert resp.json() == {"inserted": 0, "total": 0}

    def test_post_rejects_malformed_payload(self, client):
        # Missing humidity
        resp = client.post("/api/environment", json={
            "readings": [{"timestamp": "2026-04-14T22:00:00Z", "temperature": 22.5}],
        })
        assert resp.status_code == 422

    def test_post_accepts_custom_source(self, client):
        readings = self._readings(2)
        client.post(
            "/api/environment",
            json={"readings": readings, "source": "test_sensor"},
        )
        resp = client.get("/api/environment")
        assert resp.status_code == 200
        for r in resp.json():
            assert r["source"] == "test_sensor"

    def test_get_returns_inserted_readings(self, client):
        readings = self._readings(3)
        client.post("/api/environment", json={"readings": readings})
        resp = client.get("/api/environment")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["timestamp"] == "2026-04-14T22:00:00Z"
        assert data[0]["temperature"] == 22.0

    def test_get_filters_by_date_range(self, client):
        readings = [
            {"timestamp": "2026-04-13T22:00:00Z", "temperature": 20.0, "humidity": 50.0},
            {"timestamp": "2026-04-14T22:00:00Z", "temperature": 22.5, "humidity": 55.0},
            {"timestamp": "2026-04-15T22:00:00Z", "temperature": 25.0, "humidity": 60.0},
        ]
        client.post("/api/environment", json={"readings": readings})
        resp = client.get(
            "/api/environment?from=2026-04-14T00:00:00Z&to=2026-04-14T23:59:59Z"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["temperature"] == 22.5

    def test_get_empty_returns_empty_list(self, client):
        resp = client.get("/api/environment")
        assert resp.status_code == 200
        assert resp.json() == []


class TestAirQualityEndpoints:
    def _readings(self, n=3):
        return [
            {
                "timestamp": f"2026-04-15T{i:02d}:00:00Z",
                "site_id": 70,
                "site_name": "Lindfield",
                "parameter": "PM2.5",
                "value": 8.0 + i * 0.5,
                "unit": "µg/m³",
                "category": "Good",
            }
            for i in range(n)
        ]

    def test_post_accepts_batch_and_returns_counts(self, client):
        readings = self._readings(5)
        resp = client.post("/api/air-quality", json={"readings": readings})
        assert resp.status_code == 201
        assert resp.json() == {"inserted": 5, "total": 5}

    def test_post_deduplicates(self, client):
        readings = self._readings(3)
        client.post("/api/air-quality", json={"readings": readings})
        resp = client.post("/api/air-quality", json={"readings": readings})
        assert resp.json() == {"inserted": 0, "total": 3}

    def test_post_empty_batch(self, client):
        resp = client.post("/api/air-quality", json={"readings": []})
        assert resp.status_code == 201
        assert resp.json() == {"inserted": 0, "total": 0}

    def test_post_accepts_null_value(self, client):
        readings = [{
            "timestamp": "2026-04-15T00:00:00Z",
            "site_id": 70, "site_name": "Lindfield",
            "value": None,
        }]
        resp = client.post("/api/air-quality", json={"readings": readings})
        assert resp.status_code == 201
        data = client.get("/api/air-quality").json()
        assert data[0]["value"] is None

    def test_get_returns_readings(self, client):
        client.post("/api/air-quality", json={"readings": self._readings(3)})
        resp = client.get("/api/air-quality")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_get_filters_by_date_range(self, client):
        readings = [
            {"timestamp": "2026-04-14T00:00:00Z", "site_id": 70,
             "site_name": "Lindfield", "value": 5.0},
            {"timestamp": "2026-04-15T00:00:00Z", "site_id": 70,
             "site_name": "Lindfield", "value": 8.5},
        ]
        client.post("/api/air-quality", json={"readings": readings})
        resp = client.get("/api/air-quality?from=2026-04-15T00:00:00Z&to=2026-04-15T23:59:59Z")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["value"] == 8.5

    def test_get_filters_by_site_id(self, client):
        readings = [
            {"timestamp": "2026-04-15T00:00:00Z", "site_id": 70,
             "site_name": "Lindfield", "value": 8.5},
            {"timestamp": "2026-04-15T00:00:00Z", "site_id": 113,
             "site_name": "Macquarie Park", "value": 10.1},
        ]
        client.post("/api/air-quality", json={"readings": readings})
        resp = client.get("/api/air-quality?site_id=70")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["site_name"] == "Lindfield"

    def test_get_empty_returns_empty_list(self, client):
        resp = client.get("/api/air-quality")
        assert resp.status_code == 200
        assert resp.json() == []
