import pytest
import os
import tempfile
from pathlib import Path


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def db(db_path):
    from db import Database
    database = Database(db_path)
    database.init()
    return database


class TestDatabaseInit:
    def test_creates_tables(self, db, db_path):
        assert db_path.exists()
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {row["name"] for row in tables}
        assert "log_entries" in table_names
        assert "ingredient_aliases" in table_names
        assert "entry_images" in table_names
        assert "push_subscriptions" in table_names


class TestLogEntries:
    def test_insert_meal_entry(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T08:30:00Z",
            entry_type="meal",
            raw_input="rice and chicken",
        )
        assert entry_id == 1
        entry = db.get_log_entry(entry_id)
        assert entry["type"] == "meal"
        assert entry["raw_input"] == "rice and chicken"
        assert entry["parse_status"] == "pending"

    def test_insert_flare_entry(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T10:00:00Z",
            entry_type="flare",
            severity=7,
            notes="itchy arms",
        )
        entry = db.get_log_entry(entry_id)
        assert entry["type"] == "flare"
        assert entry["severity"] == 7
        assert entry["notes"] == "itchy arms"

    def test_insert_medication_entry(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T09:00:00Z",
            entry_type="medication",
            medication_name="cetirizine",
            medication_dose="10mg",
        )
        entry = db.get_log_entry(entry_id)
        assert entry["medication_name"] == "cetirizine"
        assert entry["medication_dose"] == "10mg"

    def test_insert_note_entry(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T11:00:00Z",
            entry_type="note",
            notes="ate out at Thai restaurant",
        )
        entry = db.get_log_entry(entry_id)
        assert entry["type"] == "note"
        assert entry["notes"] == "ate out at Thai restaurant"

    def test_list_entries_with_type_filter(self, db):
        db.insert_log_entry(timestamp="2026-03-23T08:00:00Z", entry_type="meal", raw_input="toast")
        db.insert_log_entry(timestamp="2026-03-23T09:00:00Z", entry_type="flare", severity=3)
        db.insert_log_entry(timestamp="2026-03-23T10:00:00Z", entry_type="meal", raw_input="rice")
        meals = db.list_log_entries(entry_type="meal")
        assert len(meals) == 2
        flares = db.list_log_entries(entry_type="flare")
        assert len(flares) == 1

    def test_list_entries_with_date_filter(self, db):
        db.insert_log_entry(timestamp="2026-03-22T08:00:00Z", entry_type="meal", raw_input="toast")
        db.insert_log_entry(timestamp="2026-03-23T08:00:00Z", entry_type="meal", raw_input="rice")
        db.insert_log_entry(timestamp="2026-03-24T08:00:00Z", entry_type="meal", raw_input="pasta")
        entries = db.list_log_entries(from_date="2026-03-23T00:00:00Z", to_date="2026-03-23T23:59:59Z")
        assert len(entries) == 1
        assert entries[0]["raw_input"] == "rice"

    def test_update_log_entry(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T08:00:00Z", entry_type="meal", raw_input="toast"
        )
        db.update_log_entry(entry_id, raw_input="toast with butter")
        entry = db.get_log_entry(entry_id)
        assert entry["raw_input"] == "toast with butter"

    def test_delete_log_entry(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T08:00:00Z", entry_type="meal", raw_input="toast"
        )
        db.delete_log_entry(entry_id)
        entry = db.get_log_entry(entry_id)
        assert entry is None

    def test_delete_log_entry_with_images(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T08:00:00Z", entry_type="meal", raw_input="toast"
        )
        db.add_image(entry_id, "/tmp/test.jpg", "2026-03-23T08:00:00Z")
        db.delete_log_entry(entry_id)
        assert db.get_log_entry(entry_id) is None
        assert db.list_images(entry_id) == []

    def test_update_parse_status(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T08:00:00Z", entry_type="meal", raw_input="rice"
        )
        db.update_parse_result(entry_id, status="parsed", ingredients='{"confirmed":["rice"],"likely":[],"source":"text"}')
        entry = db.get_log_entry(entry_id)
        assert entry["parse_status"] == "parsed"
        assert "rice" in entry["parsed_ingredients"]


class TestIngredientAliases:
    def test_add_and_resolve_alias(self, db):
        db.add_alias("tamari", "soy sauce")
        assert db.resolve_alias("tamari") == "soy sauce"
        assert db.resolve_alias("rice") == "rice"

    def test_list_aliases(self, db):
        db.add_alias("tamari", "soy sauce")
        db.add_alias("capsicum", "bell pepper")
        aliases = db.list_aliases()
        assert len(aliases) == 2


class TestEntryImages:
    def test_add_and_list_images(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T08:00:00Z", entry_type="meal", raw_input="rice"
        )
        db.add_image(entry_id, "2026/03/23/abc123.jpg", "2026-03-23T08:00:00Z")
        images = db.list_images(entry_id)
        assert len(images) == 1
        assert images[0]["image_path"] == "2026/03/23/abc123.jpg"


class TestPushSubscriptions:
    def test_add_subscription(self, db):
        db.add_push_subscription(
            endpoint="https://push.example.com/sub1",
            keys_json='{"p256dh":"key1","auth":"auth1"}',
        )
        subs = db.list_push_subscriptions()
        assert len(subs) == 1
        assert subs[0]["endpoint"] == "https://push.example.com/sub1"

    def test_duplicate_endpoint_updates(self, db):
        db.add_push_subscription("https://push.example.com/sub1", '{"p256dh":"key1","auth":"auth1"}')
        db.add_push_subscription("https://push.example.com/sub1", '{"p256dh":"key2","auth":"auth2"}')
        subs = db.list_push_subscriptions()
        assert len(subs) == 1
        assert "key2" in subs[0]["keys_json"]
