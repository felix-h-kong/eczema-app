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


def _mock_off_response(status, product=None):
    """Mock an Open Food Facts response."""
    resp = MagicMock()
    resp.status_code = 200
    payload = {"status": status}
    if product:
        payload["product"] = product
    resp.json.return_value = payload
    return resp


def _mock_upcitemdb_response(status_code=200, items=None):
    """Mock a UPC Item DB response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"items": items or []}
    return resp


class TestBarcodeEndpoint:
    @patch("main.httpx.get")
    def test_barcode_lookup_success_off(self, mock_get, client):
        """Open Food Facts has the product — should return it."""
        mock_get.return_value = _mock_off_response(1, {
            "ingredients_text": "wheat flour, sugar, palm oil, salt",
            "product_name": "Biscuits",
        })

        resp = client.post("/api/barcode/1234567890")
        assert resp.status_code == 200
        assert "wheat flour" in resp.json()["ingredients"]
        assert resp.json()["name"] == "Biscuits"

    @patch("main.httpx.get")
    def test_barcode_fallback_to_upcitemdb(self, mock_get, client):
        """Open Food Facts misses, UPC Item DB finds it."""
        mock_get.side_effect = [
            _mock_off_response(0),  # OFF miss
            _mock_upcitemdb_response(200, [{
                "title": "Whittaker's Hazella Chocolate",
                "description": "hazelnuts, cocoa butter, sugar, milk solids",
            }]),
        ]

        resp = client.post("/api/barcode/9400550003")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Whittaker's Hazella Chocolate"
        assert "hazelnuts" in resp.json()["ingredients"]

    @patch("main.httpx.get")
    def test_barcode_upcitemdb_name_only(self, mock_get, client):
        """UPC Item DB has name but no ingredients — 404 with helpful message."""
        mock_get.side_effect = [
            _mock_off_response(0),
            _mock_upcitemdb_response(200, [{"title": "Mystery Bar", "description": ""}]),
        ]

        resp = client.post("/api/barcode/0000000001")
        assert resp.status_code == 404
        assert "Mystery Bar" in resp.json()["detail"]

    @patch("main.httpx.get")
    def test_barcode_not_found_anywhere(self, mock_get, client):
        """Neither service has the product."""
        mock_get.side_effect = [
            _mock_off_response(0),
            _mock_upcitemdb_response(200, []),
        ]

        resp = client.post("/api/barcode/0000000000")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
