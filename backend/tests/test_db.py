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
        assert "environment_readings" in table_names
        assert "air_quality_readings" in table_names


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


class TestIngredientCompositions:
    def test_add_and_get_components(self, db):
        db.add_composition("continental chicken stock pot",
                           ["yeast extract", "salt", "msg"], source="manual")
        assert db.get_components("continental chicken stock pot") == ["yeast extract", "salt", "msg"]

    def test_add_composition_lowercases_and_strips(self, db):
        db.add_composition("  Continental Chicken Stock Pot  ",
                           ["  Yeast Extract ", "SALT"], source="manual")
        assert db.get_components("continental chicken stock pot") == ["yeast extract", "salt"]

    def test_add_composition_replaces_existing(self, db):
        db.add_composition("tomato sauce", ["tomato", "salt"], source="manual")
        db.add_composition("tomato sauce", ["tomato", "vinegar", "sugar"], source="manual")
        assert db.get_components("tomato sauce") == ["tomato", "vinegar", "sugar"]

    def test_add_composition_skips_blank_children(self, db):
        db.add_composition("x", ["a", "", "  ", "b"], source="manual")
        assert db.get_components("x") == ["a", "b"]

    def test_get_components_missing_returns_empty(self, db):
        assert db.get_components("nonexistent") == []

    def test_list_compositions_groups_by_parent(self, db):
        db.add_composition("stock pot", ["yeast extract", "salt"], source="manual")
        db.add_composition("vegemite", ["yeast extract", "salt", "malt extract"], source="barcode")
        listing = db.list_compositions()
        assert len(listing) == 2
        by_parent = {c["parent"]: c for c in listing}
        assert by_parent["stock pot"]["children"] == ["yeast extract", "salt"]
        assert by_parent["stock pot"]["source"] == "manual"
        assert by_parent["vegemite"]["children"] == ["yeast extract", "salt", "malt extract"]
        assert by_parent["vegemite"]["source"] == "barcode"

    def test_delete_composition(self, db):
        db.add_composition("stock pot", ["yeast extract"], source="manual")
        db.delete_composition("stock pot")
        assert db.get_components("stock pot") == []


class TestResolveIngredient:
    def test_no_alias_no_composition_returns_self(self, db):
        assert db.resolve_ingredient("rice") == [("rice", None)]

    def test_lowercases_and_strips(self, db):
        assert db.resolve_ingredient("  Rice  ") == [("rice", None)]

    def test_empty_or_none_returns_empty(self, db):
        assert db.resolve_ingredient("") == []
        assert db.resolve_ingredient("   ") == []
        assert db.resolve_ingredient(None) == []

    def test_alias_only_returns_canonical(self, db):
        db.add_alias("tamari", "soy sauce")
        assert db.resolve_ingredient("tamari") == [("soy sauce", None)]

    def test_composition_only_expands_with_provenance(self, db):
        db.add_composition("stock pot", ["yeast extract", "salt"], source="manual")
        result = db.resolve_ingredient("stock pot")
        assert result == [("yeast extract", "stock pot"), ("salt", "stock pot")]

    def test_alias_then_composition(self, db):
        db.add_alias("chicken stock cube", "continental chicken stock pot")
        db.add_composition("continental chicken stock pot",
                           ["yeast extract", "salt", "msg"], source="manual")
        result = db.resolve_ingredient("Chicken Stock Cube")
        assert result == [
            ("yeast extract", "continental chicken stock pot"),
            ("salt", "continental chicken stock pot"),
            ("msg", "continental chicken stock pot"),
        ]

    def test_single_level_expansion_only(self, db):
        # If a child is itself a composition parent, we do NOT recurse.
        db.add_composition("vegemite", ["yeast extract", "salt"], source="manual")
        db.add_composition("yeast extract", ["should-not-recurse"], source="manual")
        result = db.resolve_ingredient("vegemite")
        assert ("yeast extract", "vegemite") in result
        assert all(c[0] != "should-not-recurse" for c in result)


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


class TestEnvironmentReadings:
    def test_insert_returns_count(self, db):
        readings = [
            {"timestamp": "2026-04-14T22:00:00Z", "temperature": 22.5, "humidity": 55.0},
            {"timestamp": "2026-04-14T22:01:00Z", "temperature": 22.6, "humidity": 55.2},
            {"timestamp": "2026-04-14T22:02:00Z", "temperature": 22.6, "humidity": 55.3},
        ]
        inserted = db.insert_environment_readings(readings)
        assert inserted == 3

    def test_insert_deduplicates_on_timestamp(self, db):
        readings = [
            {"timestamp": "2026-04-14T22:00:00Z", "temperature": 22.5, "humidity": 55.0},
            {"timestamp": "2026-04-14T22:01:00Z", "temperature": 22.6, "humidity": 55.2},
        ]
        first = db.insert_environment_readings(readings)
        assert first == 2
        second = db.insert_environment_readings(readings)
        assert second == 0

    def test_insert_partial_overlap(self, db):
        batch_a = [
            {"timestamp": "2026-04-14T22:00:00Z", "temperature": 22.5, "humidity": 55.0},
            {"timestamp": "2026-04-14T22:01:00Z", "temperature": 22.6, "humidity": 55.2},
        ]
        batch_b = [
            {"timestamp": "2026-04-14T22:01:00Z", "temperature": 22.6, "humidity": 55.2},
            {"timestamp": "2026-04-14T22:02:00Z", "temperature": 22.7, "humidity": 55.4},
        ]
        db.insert_environment_readings(batch_a)
        inserted = db.insert_environment_readings(batch_b)
        assert inserted == 1

    def test_insert_with_source(self, db):
        readings = [{"timestamp": "2026-04-14T22:00:00Z", "temperature": 22.5, "humidity": 55.0}]
        db.insert_environment_readings(readings, source="test_source")
        rows = db.list_environment_readings()
        assert len(rows) == 1
        assert rows[0]["source"] == "test_source"

    def test_insert_default_source_is_govee_h5075(self, db):
        readings = [{"timestamp": "2026-04-14T22:00:00Z", "temperature": 22.5, "humidity": 55.0}]
        db.insert_environment_readings(readings)
        rows = db.list_environment_readings()
        assert rows[0]["source"] == "govee_h5075"

    def test_list_orders_by_timestamp_ascending(self, db):
        readings = [
            {"timestamp": "2026-04-14T22:02:00Z", "temperature": 22.7, "humidity": 55.4},
            {"timestamp": "2026-04-14T22:00:00Z", "temperature": 22.5, "humidity": 55.0},
            {"timestamp": "2026-04-14T22:01:00Z", "temperature": 22.6, "humidity": 55.2},
        ]
        db.insert_environment_readings(readings)
        rows = db.list_environment_readings()
        timestamps = [r["timestamp"] for r in rows]
        assert timestamps == [
            "2026-04-14T22:00:00Z",
            "2026-04-14T22:01:00Z",
            "2026-04-14T22:02:00Z",
        ]

    def test_list_filters_by_date_range(self, db):
        readings = [
            {"timestamp": "2026-04-13T22:00:00Z", "temperature": 20.0, "humidity": 50.0},
            {"timestamp": "2026-04-14T22:00:00Z", "temperature": 22.5, "humidity": 55.0},
            {"timestamp": "2026-04-15T22:00:00Z", "temperature": 25.0, "humidity": 60.0},
        ]
        db.insert_environment_readings(readings)
        rows = db.list_environment_readings(
            from_date="2026-04-14T00:00:00Z",
            to_date="2026-04-14T23:59:59Z",
        )
        assert len(rows) == 1
        assert rows[0]["temperature"] == 22.5

    def test_list_empty_returns_empty_list(self, db):
        assert db.list_environment_readings() == []


class TestAirQualityReadings:
    def _reading(self, ts="2026-04-15T00:00:00Z", site_id=70, site_name="Lindfield",
                 value=8.5, category="Good"):
        return {"timestamp": ts, "site_id": site_id, "site_name": site_name,
                "value": value, "category": category}

    def test_insert_returns_count(self, db):
        readings = [
            self._reading(ts="2026-04-15T00:00:00Z"),
            self._reading(ts="2026-04-15T01:00:00Z"),
        ]
        assert db.insert_air_quality_readings(readings) == 2

    def test_insert_deduplicates_on_timestamp_site_parameter(self, db):
        readings = [self._reading()]
        assert db.insert_air_quality_readings(readings) == 1
        assert db.insert_air_quality_readings(readings) == 0

    def test_insert_different_sites_same_timestamp(self, db):
        readings = [
            self._reading(site_id=70, site_name="Lindfield"),
            self._reading(site_id=113, site_name="Macquarie Park"),
        ]
        assert db.insert_air_quality_readings(readings) == 2

    def test_insert_null_value(self, db):
        readings = [self._reading(value=None, category=None)]
        assert db.insert_air_quality_readings(readings) == 1
        rows = db.list_air_quality_readings()
        assert rows[0]["value"] is None

    def test_insert_empty_list(self, db):
        assert db.insert_air_quality_readings([]) == 0

    def test_insert_with_custom_source(self, db):
        readings = [self._reading()]
        db.insert_air_quality_readings(readings, source="test_source")
        rows = db.list_air_quality_readings()
        assert rows[0]["source"] == "test_source"

    def test_list_filters_by_date_range(self, db):
        readings = [
            self._reading(ts="2026-04-14T00:00:00Z", value=5.0),
            self._reading(ts="2026-04-15T00:00:00Z", value=8.5),
            self._reading(ts="2026-04-16T00:00:00Z", value=15.0),
        ]
        db.insert_air_quality_readings(readings)
        rows = db.list_air_quality_readings(
            from_date="2026-04-15T00:00:00Z",
            to_date="2026-04-15T23:59:59Z",
        )
        assert len(rows) == 1
        assert rows[0]["value"] == 8.5

    def test_list_filters_by_site_id(self, db):
        readings = [
            self._reading(site_id=70, site_name="Lindfield"),
            self._reading(site_id=113, site_name="Macquarie Park"),
        ]
        db.insert_air_quality_readings(readings)
        rows = db.list_air_quality_readings(site_id=70)
        assert len(rows) == 1
        assert rows[0]["site_name"] == "Lindfield"

    def test_list_orders_by_timestamp_ascending(self, db):
        readings = [
            self._reading(ts="2026-04-15T02:00:00Z"),
            self._reading(ts="2026-04-15T00:00:00Z"),
            self._reading(ts="2026-04-15T01:00:00Z"),
        ]
        db.insert_air_quality_readings(readings)
        rows = db.list_air_quality_readings()
        timestamps = [r["timestamp"] for r in rows]
        assert timestamps == [
            "2026-04-15T00:00:00Z",
            "2026-04-15T01:00:00Z",
            "2026-04-15T02:00:00Z",
        ]

    def test_list_empty_returns_empty_list(self, db):
        assert db.list_air_quality_readings() == []
