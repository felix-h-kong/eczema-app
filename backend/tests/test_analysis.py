import pytest
import json
from unittest.mock import MagicMock, patch


def make_db_with_data(entries, aliases=None):
    """Helper to create a real db with test data."""
    from db import Database
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp()) / "test.db"
    db = Database(tmp)
    db.init()

    for e in entries:
        entry_id = db.insert_log_entry(
            timestamp=e["timestamp"],
            entry_type=e["type"],
            raw_input=e.get("raw_input"),
            severity=e.get("severity"),
            medication_name=e.get("medication_name"),
            notes=e.get("notes"),
        )
        if "ingredients" in e:
            db.update_parse_result(
                entry_id,
                status="parsed",
                ingredients=json.dumps(e["ingredients"]),
            )

    for alias in (aliases or []):
        db.add_alias(alias["variant"], alias["canonical"])

    return db


class TestCorrelation:
    def test_basic_correlation(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "milk and cereal",
             "ingredients": {"confirmed": ["milk", "cereal"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
            {"timestamp": "2026-03-21T08:00:00Z", "type": "meal", "raw_input": "rice and chicken",
             "ingredients": {"confirmed": ["rice", "chicken"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "cheese sandwich",
             "ingredients": {"confirmed": ["cheese", "bread"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 6},
        ])

        result = compute_correlation(db, use_likely=False)
        assert "stats" in result
        assert "flare_count" in result

    def test_ingredient_appearing_in_multiple_flares(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "milk",
             "ingredients": {"confirmed": ["milk", "cereal"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
            {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "milk",
             "ingredients": {"confirmed": ["milk", "rice"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 6},
            {"timestamp": "2026-03-24T08:00:00Z", "type": "meal", "raw_input": "chicken",
             "ingredients": {"confirmed": ["chicken", "rice"], "likely": [], "source": "text"}},
        ])

        result = compute_correlation(db, use_likely=False)
        stats = result["stats"]
        milk_stat = next((s for s in stats if s["ingredient"] == "milk"), None)
        assert milk_stat is not None
        assert milk_stat["flare_appearances"] >= 2
        assert milk_stat["lift"] > 1.0

    def test_alias_resolution(self):
        from analysis import compute_correlation

        db = make_db_with_data(
            entries=[
                {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "tamari rice",
                 "ingredients": {"confirmed": ["tamari", "rice"], "likely": [], "source": "text"}},
                {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
                {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "soy sauce noodles",
                 "ingredients": {"confirmed": ["soy sauce", "noodles"], "likely": [], "source": "text"}},
                {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 6},
                {"timestamp": "2026-03-24T08:00:00Z", "type": "meal", "raw_input": "plain rice",
                 "ingredients": {"confirmed": ["rice"], "likely": [], "source": "text"}},
            ],
            aliases=[{"variant": "tamari", "canonical": "soy sauce"}],
        )

        result = compute_correlation(db, use_likely=False)
        stats = result["stats"]
        soy_stat = next((s for s in stats if s["ingredient"] == "soy sauce"), None)
        assert soy_stat is not None
        assert soy_stat["flare_appearances"] == 2

    def test_medication_confounding(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "milk",
             "ingredients": {"confirmed": ["milk"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-20T14:00:00Z", "type": "medication", "medication_name": "cetirizine"},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
            {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "milk",
             "ingredients": {"confirmed": ["milk"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 6},
        ])

        result = compute_correlation(db, use_likely=False)
        stats = result["stats"]
        milk_stat = next((s for s in stats if s["ingredient"] == "milk"), None)
        assert milk_stat is not None
        assert milk_stat["confounded"] >= 1

    def test_low_flare_warning(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "rice",
             "ingredients": {"confirmed": ["rice"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 5},
        ])

        result = compute_correlation(db, use_likely=False)
        assert result["warning"] is not None

    def test_use_likely_flag(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "stir fry",
             "ingredients": {"confirmed": ["rice"], "likely": ["soy sauce"], "source": "text"}},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
            {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "stir fry",
             "ingredients": {"confirmed": ["rice"], "likely": ["soy sauce"], "source": "text"}},
            {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 6},
            {"timestamp": "2026-03-24T08:00:00Z", "type": "meal", "raw_input": "plain rice",
             "ingredients": {"confirmed": ["rice"], "likely": [], "source": "text"}},
        ])

        result_without = compute_correlation(db, use_likely=False)
        result_with = compute_correlation(db, use_likely=True)

        soy_without = next((s for s in result_without["stats"] if s["ingredient"] == "soy sauce"), None)
        soy_with = next((s for s in result_with["stats"] if s["ingredient"] == "soy sauce"), None)

        assert soy_without is None
        assert soy_with is not None
