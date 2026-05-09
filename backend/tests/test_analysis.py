import pytest
import json
from unittest.mock import MagicMock, patch

# Pin flare config for all tests so they don't depend on config/analysis.txt
@pytest.fixture(autouse=True)
def _pin_flare_config():
    with patch("analysis.get_flare_config", return_value=(3, 3)):
        yield


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


def _baseline_checks(start_date="2026-03-18", severity=3):
    """Generate 3 baseline skin checks at low severity before test data."""
    return [
        {"timestamp": f"{start_date}T08:00:00Z", "type": "flare", "severity": severity},
        {"timestamp": f"{start_date}T14:00:00Z", "type": "flare", "severity": severity},
        {"timestamp": f"{start_date}T20:00:00Z", "type": "flare", "severity": severity},
    ]


class TestFlareDetection:
    def test_rising_edge_detected(self):
        """A jump from avg 3 to 7 (+4) should be detected as a flare."""
        from analysis import _detect_flares
        entries = [
            *_baseline_checks(),
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
        ]
        flares = _detect_flares(entries)
        assert len(flares) == 1
        assert flares[0]["severity"] == 7

    def test_steady_high_not_detected(self):
        """Steady severity 7 should NOT be detected — no rising edge."""
        from analysis import _detect_flares
        entries = [
            *_baseline_checks(severity=7),
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
        ]
        flares = _detect_flares(entries)
        assert len(flares) == 0

    def test_gradual_rise_not_detected(self):
        """Gradual rise (each step < 3) should not trigger."""
        from analysis import _detect_flares
        entries = [
            {"timestamp": "2026-03-18T08:00:00Z", "type": "flare", "severity": 3},
            {"timestamp": "2026-03-18T14:00:00Z", "type": "flare", "severity": 4},
            {"timestamp": "2026-03-18T20:00:00Z", "type": "flare", "severity": 5},
            {"timestamp": "2026-03-19T08:00:00Z", "type": "flare", "severity": 6},
        ]
        flares = _detect_flares(entries)
        assert len(flares) == 0

    def test_spike_then_return(self):
        """Only the spike should be a flare, not the return to baseline."""
        from analysis import _detect_flares
        entries = [
            *_baseline_checks(),
            {"timestamp": "2026-03-20T08:00:00Z", "type": "flare", "severity": 8},
            {"timestamp": "2026-03-20T14:00:00Z", "type": "flare", "severity": 3},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 3},
        ]
        flares = _detect_flares(entries)
        assert len(flares) == 1
        assert flares[0]["severity"] == 8

    def test_same_day_kept_separate(self):
        """Multiple rising edges on the same day are kept as separate per-check anchors."""
        from analysis import _detect_flares
        entries = [
            *_baseline_checks(),
            {"timestamp": "2026-03-20T08:00:00Z", "type": "flare", "severity": 6},
            {"timestamp": "2026-03-20T14:00:00Z", "type": "flare", "severity": 8},
        ]
        flares = _detect_flares(entries)
        assert len(flares) == 2
        severities = {f["severity"] for f in flares}
        assert severities == {6, 8}

    def test_not_enough_history(self):
        """With fewer than FLARE_ROLLING_WINDOW prior entries, no flares detected."""
        from analysis import _detect_flares
        entries = [
            {"timestamp": "2026-03-18T08:00:00Z", "type": "flare", "severity": 3},
            {"timestamp": "2026-03-18T14:00:00Z", "type": "flare", "severity": 9},
        ]
        flares = _detect_flares(entries)
        assert len(flares) == 0


class TestCorrelation:
    def test_basic_correlation(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            *_baseline_checks(),
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "milk and cereal",
             "ingredients": {"confirmed": ["milk", "cereal"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
            {"timestamp": "2026-03-21T08:00:00Z", "type": "meal", "raw_input": "rice and chicken",
             "ingredients": {"confirmed": ["rice", "chicken"], "likely": [], "source": "text"}},
        ])

        result = compute_correlation(db, use_likely=False)
        assert "stats" in result
        assert "flare_count" in result
        assert result["flare_count"] == 1

    def test_ingredient_appearing_in_multiple_flares(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            *_baseline_checks(),
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "milk",
             "ingredients": {"confirmed": ["milk", "cereal"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
            # Severity drops back down
            {"timestamp": "2026-03-21T08:00:00Z", "type": "flare", "severity": 3},
            {"timestamp": "2026-03-21T14:00:00Z", "type": "flare", "severity": 3},
            {"timestamp": "2026-03-21T20:00:00Z", "type": "flare", "severity": 3},
            # Second flare
            {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "milk",
             "ingredients": {"confirmed": ["milk", "rice"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 7},
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
                *_baseline_checks(),
                {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "tamari rice",
                 "ingredients": {"confirmed": ["tamari", "rice"], "likely": [], "source": "text"}},
                {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
                # Recovery
                {"timestamp": "2026-03-21T08:00:00Z", "type": "flare", "severity": 3},
                {"timestamp": "2026-03-21T14:00:00Z", "type": "flare", "severity": 3},
                {"timestamp": "2026-03-21T20:00:00Z", "type": "flare", "severity": 3},
                # Second flare
                {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "soy sauce noodles",
                 "ingredients": {"confirmed": ["soy sauce", "noodles"], "likely": [], "source": "text"}},
                {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 7},
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
            *_baseline_checks(),
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "milk",
             "ingredients": {"confirmed": ["milk"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-20T14:00:00Z", "type": "medication", "medication_name": "cetirizine"},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
            # Recovery
            {"timestamp": "2026-03-21T08:00:00Z", "type": "flare", "severity": 3},
            {"timestamp": "2026-03-21T14:00:00Z", "type": "flare", "severity": 3},
            {"timestamp": "2026-03-21T20:00:00Z", "type": "flare", "severity": 3},
            # Second flare (no medication)
            {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "milk",
             "ingredients": {"confirmed": ["milk"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 7},
        ])

        result = compute_correlation(db, use_likely=False)
        stats = result["stats"]
        milk_stat = next((s for s in stats if s["ingredient"] == "milk"), None)
        assert milk_stat is not None
        assert milk_stat["confounded"] >= 1

    def test_low_flare_warning(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            *_baseline_checks(),
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "rice",
             "ingredients": {"confirmed": ["rice"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 5},
        ])

        result = compute_correlation(db, use_likely=False)
        assert result["warning"] is not None

    def test_use_likely_flag(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            *_baseline_checks(),
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "stir fry",
             "ingredients": {"confirmed": ["rice"], "likely": ["soy sauce"], "source": "text"}},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
            # Recovery
            {"timestamp": "2026-03-21T08:00:00Z", "type": "flare", "severity": 3},
            {"timestamp": "2026-03-21T14:00:00Z", "type": "flare", "severity": 3},
            {"timestamp": "2026-03-21T20:00:00Z", "type": "flare", "severity": 3},
            # Second flare
            {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "stir fry",
             "ingredients": {"confirmed": ["rice"], "likely": ["soy sauce"], "source": "text"}},
            {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 7},
            {"timestamp": "2026-03-24T08:00:00Z", "type": "meal", "raw_input": "plain rice",
             "ingredients": {"confirmed": ["rice"], "likely": [], "source": "text"}},
        ])

        result_without = compute_correlation(db, use_likely=False)
        result_with = compute_correlation(db, use_likely=True)

        soy_without = next((s for s in result_without["stats"] if s["ingredient"] == "soy sauce"), None)
        soy_with = next((s for s in result_with["stats"] if s["ingredient"] == "soy sauce"), None)

        assert soy_without is None
        assert soy_with is not None
