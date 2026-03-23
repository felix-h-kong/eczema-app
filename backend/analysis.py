"""
Correlation algorithm: identifies food ingredients that correlate with eczema flares.

Algorithm:
1. Resolve all ingredient names through ingredient_aliases table
2. For each flare event, define pre-flare window: meals in 6-48h before the flare
3. Collect ingredients from meals in flare windows → flare ingredient set
4. Collect ingredients from meals outside any flare window → baseline ingredient set
5. Per ingredient, compute: flare_freq, baseline_freq, lift, flare_appearances
6. Flag confounded flare events: medication within ±12h of flare
7. Filter to ingredients with >= MIN_FLARE_APPEARANCES flare appearances
8. Sort by lift descending
9. Return structured results
"""

import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from config import (
    FLARE_WINDOW_HOURS,
    MEDICATION_CONFOUND_HOURS,
    MIN_FLARE_APPEARANCES,
    LOW_FLARE_WARNING_THRESHOLD,
)


def _parse_ts(ts_str: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a timezone-aware datetime."""
    ts_str = ts_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _get_ingredients(entry: dict, use_likely: bool) -> list[str]:
    """Extract ingredient names from a parsed log entry."""
    raw = entry.get("parsed_ingredients")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    ingredients = list(data.get("confirmed", []))
    if use_likely:
        ingredients += list(data.get("likely", []))
    return ingredients


def compute_correlation(db, use_likely: bool = False) -> dict:
    """
    Compute ingredient-flare correlations.

    Args:
        db: Database instance with list_log_entries and resolve_alias methods.
        use_likely: If True, include "likely" ingredients alongside "confirmed" ones.

    Returns:
        {
            "stats": [
                {
                    "ingredient": str,
                    "lift": float,
                    "flare_freq": float,
                    "baseline_freq": float,
                    "flare_appearances": int,
                    "confounded": int,
                }
            ],
            "flare_count": int,
            "warning": str | None,
        }
    """
    # --- 1. Load all relevant entries ---
    flares = db.list_log_entries(entry_type="flare")
    meals = db.list_log_entries(entry_type="meal")
    medications = db.list_log_entries(entry_type="medication")

    flare_count = len(flares)

    warning = None
    if flare_count < LOW_FLARE_WARNING_THRESHOLD:
        warning = (
            f"Only {flare_count} flare event(s) recorded. "
            f"At least {LOW_FLARE_WARNING_THRESHOLD} are recommended for reliable correlation analysis."
        )

    if flare_count == 0:
        return {"stats": [], "flare_count": 0, "warning": warning}

    window_min_h, window_max_h = FLARE_WINDOW_HOURS

    # --- 2. Build flare windows ---
    # Each flare defines a window [flare_ts - window_max_h, flare_ts - window_min_h]
    flare_windows = []
    for flare in flares:
        flare_ts = _parse_ts(flare["timestamp"])
        window_start = flare_ts - timedelta(hours=window_max_h)
        window_end = flare_ts - timedelta(hours=window_min_h)
        flare_windows.append((flare_ts, window_start, window_end))

    # --- 3. Determine which meals fall inside / outside any flare window ---
    # For each flare window, collect (resolved) ingredient sets
    # flare_ingredient_sets[i] = set of resolved ingredient names for flare i
    flare_ingredient_sets: list[set] = [set() for _ in flare_windows]
    baseline_ingredients: set = set()  # ingredient names that appear in baseline meals

    # We also need counts for frequency calculations
    # flare_meal_counts[i] = number of unique meal entries in flare window i
    flare_meal_counts = [0] * len(flare_windows)
    baseline_meal_count = 0

    # Track which flare windows each ingredient appears in (for flare_appearances)
    # ingredient -> set of flare indices
    ingredient_flare_indices: dict[str, set] = defaultdict(set)
    # ingredient -> count in baseline
    ingredient_baseline_count: dict[str, int] = defaultdict(int)

    for meal in meals:
        meal_ts = _parse_ts(meal["timestamp"])
        ingredients_raw = _get_ingredients(meal, use_likely)

        # Resolve aliases
        ingredients = [db.resolve_alias(ing) for ing in ingredients_raw]

        # Check which flare windows this meal falls into
        matched_windows = []
        for i, (flare_ts, window_start, window_end) in enumerate(flare_windows):
            if window_start <= meal_ts <= window_end:
                matched_windows.append(i)

        if matched_windows:
            for i in matched_windows:
                flare_meal_counts[i] += 1
                for ing in ingredients:
                    flare_ingredient_sets[i].add(ing)
                    ingredient_flare_indices[ing].add(i)
        else:
            baseline_meal_count += 1
            for ing in ingredients:
                baseline_ingredients.add(ing)
                ingredient_baseline_count[ing] += 1

    # --- 6. Detect confounded flare events (medication within ±MEDICATION_CONFOUND_HOURS) ---
    confound_window = timedelta(hours=MEDICATION_CONFOUND_HOURS)
    confounded_flare_indices: set = set()
    for med in medications:
        med_ts = _parse_ts(med["timestamp"])
        for i, (flare_ts, _, _) in enumerate(flare_windows):
            if abs(med_ts - flare_ts) <= confound_window:
                confounded_flare_indices.add(i)

    # --- 5. Compute per-ingredient statistics ---
    # Total flare windows (denominator for flare_freq)
    total_flare_windows = len(flare_windows)

    # Collect all ingredients that appear in any flare window
    all_flare_ingredients = set()
    for s in flare_ingredient_sets:
        all_flare_ingredients.update(s)

    stats = []
    for ing in all_flare_ingredients:
        flare_appearances = len(ingredient_flare_indices[ing])

        # Filter: must appear in at least MIN_FLARE_APPEARANCES flare windows
        if flare_appearances < MIN_FLARE_APPEARANCES:
            continue

        # flare_freq: fraction of flare windows where ingredient appeared
        flare_freq = flare_appearances / total_flare_windows

        # baseline_freq: fraction of baseline meals where ingredient appeared
        if baseline_meal_count > 0:
            baseline_freq = ingredient_baseline_count[ing] / baseline_meal_count
        else:
            baseline_freq = 0.0

        # lift: flare_freq / baseline_freq (handle zero baseline)
        if baseline_freq > 0:
            lift = flare_freq / baseline_freq
        else:
            # Ingredient never seen in baseline → maximum correlation signal
            lift = float("inf") if flare_freq > 0 else 1.0

        # confounded: number of flare windows this ingredient appears in that are also confounded
        confounded_count = len(ingredient_flare_indices[ing] & confounded_flare_indices)

        stats.append(
            {
                "ingredient": ing,
                "lift": lift,
                "flare_freq": flare_freq,
                "baseline_freq": baseline_freq,
                "flare_appearances": flare_appearances,
                "confounded": confounded_count,
            }
        )

    # --- 8. Sort by lift descending ---
    stats.sort(key=lambda s: s["lift"], reverse=True)

    return {
        "stats": stats,
        "flare_count": flare_count,
        "warning": warning,
    }
