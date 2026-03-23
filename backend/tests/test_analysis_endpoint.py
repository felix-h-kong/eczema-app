import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_data(tmp_path):
    import config
    config.DB_PATH = tmp_path / "test.db"
    config.DATA_DIR = tmp_path
    config.IMAGES_DIR = tmp_path / "images"

    from main import app, get_db
    from db import Database

    db = Database(config.DB_PATH)
    db.init()

    # Seed with enough data for analysis
    for day in range(1, 15):
        ts = f"2026-03-{day:02d}T08:00:00Z"
        entry_id = db.insert_log_entry(timestamp=ts, entry_type="meal", raw_input="rice and chicken")
        db.update_parse_result(entry_id, "parsed",
            json.dumps({"confirmed": ["rice", "chicken"], "likely": ["soy sauce"], "source": "text"}))

    # Add some meals with milk before flares
    for day in [5, 10]:
        ts = f"2026-03-{day:02d}T12:00:00Z"
        entry_id = db.insert_log_entry(timestamp=ts, entry_type="meal", raw_input="milk and cereal")
        db.update_parse_result(entry_id, "parsed",
            json.dumps({"confirmed": ["milk", "cereal"], "likely": [], "source": "text"}))
        flare_ts = f"2026-03-{day:02d}T22:00:00Z"
        db.insert_log_entry(timestamp=flare_ts, entry_type="flare", severity=7)

    def override_get_db():
        return db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestAnalyseEndpoint:
    def test_start_analysis(self, client_with_data):
        resp = client_with_data.post("/api/analyse", json={"use_likely": False})
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data

    @patch("main._get_analysis_summary", return_value="Test summary: milk appears correlated with flares.")
    def test_get_analysis_result(self, mock_summary, client_with_data):
        resp = client_with_data.post("/api/analyse", json={"use_likely": False})
        job_id = resp.json()["job_id"]

        import time
        for _ in range(10):
            resp = client_with_data.get(f"/api/analyse/{job_id}")
            assert resp.status_code == 200
            data = resp.json()
            if data["status"] == "complete":
                assert "stats" in data
                assert "summary" in data
                assert "milk" in data["summary"].lower()
                return
            time.sleep(0.2)

        assert data["status"] in ("complete", "running")

    def test_nonexistent_job_returns_404(self, client_with_data):
        resp = client_with_data.get("/api/analyse/nonexistent")
        assert resp.status_code == 404
