import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


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


class TestBarcodeEndpoint:
    @patch("main.httpx")
    def test_barcode_lookup_success(self, mock_httpx, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": 1,
            "product": {
                "ingredients_text": "wheat flour, sugar, palm oil, salt"
            }
        }
        mock_httpx.get.return_value = mock_response

        resp = client.post("/api/barcode/1234567890")
        assert resp.status_code == 200
        assert "wheat flour" in resp.json()["ingredients"]

    @patch("main.httpx")
    def test_barcode_not_found(self, mock_httpx, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": 0}
        mock_httpx.get.return_value = mock_response

        resp = client.post("/api/barcode/0000000000")
        assert resp.status_code == 404
