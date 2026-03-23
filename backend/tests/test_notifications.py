import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta


class TestShouldNotify:
    def test_should_notify_when_no_recent_meal(self):
        from notifications import should_send_notification

        mock_db = MagicMock()
        mock_db.list_log_entries.return_value = []

        assert should_send_notification(mock_db) is True

    def test_should_not_notify_when_recent_meal(self):
        from notifications import should_send_notification

        mock_db = MagicMock()
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        mock_db.list_log_entries.return_value = [
            {"timestamp": recent, "type": "meal"},
        ]

        assert should_send_notification(mock_db) is False


class TestSendNotifications:
    def test_send_to_all_subscribers(self):
        from notifications import send_meal_reminder

        mock_db = MagicMock()
        mock_db.list_log_entries.return_value = []
        mock_db.list_push_subscriptions.return_value = [
            {"endpoint": "https://push.example.com/1", "keys_json": '{"p256dh":"k1","auth":"a1"}'},
            {"endpoint": "https://push.example.com/2", "keys_json": '{"p256dh":"k2","auth":"a2"}'},
        ]

        with patch("notifications.webpush") as mock_push:
            send_meal_reminder(mock_db, "Time to log lunch")
            assert mock_push.call_count == 2
