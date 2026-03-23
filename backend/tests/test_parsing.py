import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock


class TestParseIngredients:
    def test_parse_text_success(self):
        from parsing import parse_ingredients_from_text

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"confirmed":["rice","chicken"],"likely":["soy sauce"],"source":"text"}')]

        with patch("parsing.get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = parse_ingredients_from_text("rice and chicken stir fry")

        assert result["confirmed"] == ["rice", "chicken"]
        assert result["likely"] == ["soy sauce"]
        assert result["source"] == "text"

    def test_parse_text_returns_none_on_api_error(self):
        from parsing import parse_ingredients_from_text

        with patch("parsing.get_client") as mock_client:
            mock_client.return_value.messages.create.side_effect = Exception("API error")
            result = parse_ingredients_from_text("rice")

        assert result is None

    def test_parse_text_returns_none_on_invalid_json(self):
        from parsing import parse_ingredients_from_text

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not json")]

        with patch("parsing.get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = parse_ingredients_from_text("rice")

        assert result is None


class TestBackgroundParsing:
    def test_process_pending_entry(self):
        from parsing import process_pending_entry

        mock_db = MagicMock()
        mock_db.get_log_entry.return_value = {
            "id": 1, "type": "meal", "raw_input": "rice and chicken",
            "parse_status": "pending",
        }

        parsed = {"confirmed": ["rice", "chicken"], "likely": [], "source": "text"}

        with patch("parsing.parse_ingredients_from_text", return_value=parsed):
            process_pending_entry(mock_db, 1)

        mock_db.update_parse_result.assert_called_once_with(
            1, status="parsed", ingredients=json.dumps(parsed)
        )

    def test_process_pending_entry_marks_failed(self):
        from parsing import process_pending_entry

        mock_db = MagicMock()
        mock_db.get_log_entry.return_value = {
            "id": 1, "type": "meal", "raw_input": "rice",
            "parse_status": "pending",
        }

        with patch("parsing.parse_ingredients_from_text", return_value=None):
            process_pending_entry(mock_db, 1)

        mock_db.update_parse_result.assert_called_once_with(1, status="failed", ingredients=None)
