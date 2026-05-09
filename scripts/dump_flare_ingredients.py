#!/usr/bin/env python3
"""Phase 1 descriptive dump: for each detected flare day, print the meals in the
6-48h pre-flare window with their (resolved) ingredients.

Visual inspection is the analysis. Ingredients that recur across multiple flare
windows are Phase 2 candidates.

Usage:
    python scripts/dump_flare_ingredients.py                    # flare dump from existing parsed state
    python scripts/dump_flare_ingredients.py --parse            # bulk-parse unparsed meals first, then dump
    python scripts/dump_flare_ingredients.py --good-days        # also show good-day windows (whitelist analog)
    python scripts/dump_flare_ingredients.py --default-storage refrigerated  # treat null storage_state as refrigerated
"""
import argparse
import json
import runpy
import sys
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from db import Database
from config import DB_PATH, FLARE_WINDOW_HOURS, get_flare_config
from analysis import _detect_flares, _parse_ts, _get_ingredients

SYDNEY = ZoneInfo("Australia/Sydney")
STORAGE_VALUES = ("fresh", "restaurant", "refrigerated", "frozen", "room_temp", "shelf_stable")


def fmt_local(ts_iso: str) -> str:
    return _parse_ts(ts_iso).astimezone(SYDNEY).strftime("%Y-%m-%d %H:%M")


def get_storage_state(meal: dict, default: str | None) -> str | None:
    """Read storage_state from parsed_ingredients JSON. Apply default if null/missing."""
    raw = meal.get("parsed_ingredients")
    if not raw:
        return default
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default
    value = data.get("storage_state")
    if value not in STORAGE_VALUES:
        return default
    return value


def detect_good_days(all_skin: list[dict], threshold: int, exclude_ids: set | None = None) -> list[dict]:
    """Return checks with severity ≤ threshold. Each check is its own anchor.

    exclude_ids: set of entry IDs to skip (typically the flare check IDs, so a check
    that is simultaneously a rising-edge flare and below the good threshold doesn't
    appear in both groups).
    """
    result = []
    for entry in all_skin:
        sev = entry.get("severity")
        if sev is None or sev > threshold:
            continue
        if exclude_ids and entry.get("id") in exclude_ids:
            continue
        result.append(entry)
    return sorted(result, key=lambda e: _parse_ts(e["timestamp"]))


def analyze_windows(
    label: str,
    anchors: list[dict],
    meals: list[dict],
    db: Database,
    win_min_h: float,
    win_max_h: float,
    use_likely: bool,
    default_storage: str | None,
) -> dict:
    """Print per-anchor blocks and return aggregates.

    Returns {
      "resolved_freq": {(name, parent): count},
      "raw_freq": {raw_name: count},
      "storage_across_windows": Counter,
      "n_anchors": int,
    }
    """
    resolved_freq: dict[tuple[str, str | None], int] = defaultdict(int)
    raw_freq: dict[str, int] = defaultdict(int)
    storage_across: Counter = Counter()

    for anchor in anchors:
        anchor_ts = _parse_ts(anchor["timestamp"])
        window_start = anchor_ts - timedelta(hours=win_max_h)
        window_end = anchor_ts - timedelta(hours=win_min_h)

        notes = (anchor.get("notes") or "").strip()
        sev = anchor.get("severity")

        print(f"=== {label}: {fmt_local(anchor['timestamp'])} (Sydney) — severity {sev} ===")
        if notes:
            print(f"  notes: {notes[:120]}")
        print(f"  pre-window: {fmt_local(window_start.isoformat())} → "
              f"{fmt_local(window_end.isoformat())}")

        meals_in_window = [
            m for m in meals if window_start <= _parse_ts(m["timestamp"]) <= window_end
        ]
        meals_in_window.sort(key=lambda m: _parse_ts(m["timestamp"]))

        if not meals_in_window:
            print("  (no meals in window)")
            print()
            continue

        pairs_in_this_anchor: set[tuple[str, str | None]] = set()
        storage_this_window: Counter = Counter()

        for meal in meals_in_window:
            raw_text = (meal.get("raw_input") or "").strip()
            display_text = raw_text[:80] if raw_text else "(image-only)"
            storage = get_storage_state(meal, default_storage)
            storage_tag = f"[{storage}]" if storage else "[storage: ?]"
            print(f"  {fmt_local(meal['timestamp'])}  {storage_tag:<20}  \"{display_text}\"")
            storage_this_window[storage or "unknown"] += 1

            raw_ings = _get_ingredients(meal, use_likely=use_likely)
            if not raw_ings:
                print("    (no parsed ingredients)")
                continue

            resolved_lines = []
            seen_in_meal: set[tuple[str, str | None]] = set()
            for r in raw_ings:
                raw_freq[r.lower().strip()] += 1
                for name, parent in db.resolve_ingredient(r):
                    if (name, parent) in seen_in_meal:
                        continue
                    seen_in_meal.add((name, parent))
                    if parent:
                        resolved_lines.append(f"      {name}  (via {parent})")
                    else:
                        resolved_lines.append(f"      {name}")
                    if (name, parent) not in pairs_in_this_anchor:
                        pairs_in_this_anchor.add((name, parent))
                        resolved_freq[(name, parent)] += 1
            if resolved_lines:
                print("    resolved:")
                for line in resolved_lines:
                    print(line)

        # Per-window storage summary
        if storage_this_window:
            parts = [f"{n}× {s}" for s, n in storage_this_window.most_common()]
            print(f"  storage mix: {', '.join(parts)}")
        for s, n in storage_this_window.items():
            storage_across[s] += n
        print()

    return {
        "resolved_freq": dict(resolved_freq),
        "raw_freq": dict(raw_freq),
        "storage_across_windows": storage_across,
        "n_anchors": len(anchors),
    }


def print_freq_table(title: str, freq: dict, n_anchors: int):
    print("=" * 78)
    print(f"{title} (n={n_anchors} windows; 1 count = ingredient appeared in at least 1 meal of that window)")
    print("-" * 78)
    if not freq:
        print("  (no ingredients)")
        return
    sorted_items = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1] or ""))
    for (name, parent), count in sorted_items:
        prov_str = f"  (via {parent})" if parent else ""
        bar = "█" * count
        print(f"  {count:>3}  {bar:<{n_anchors}}  {name}{prov_str}")


def print_rr_view(flare_freq: dict, good_freq: dict, flare_n: int, good_n: int, top_k: int = 25):
    """Print flare-vs-good comparison using risk ratios.

    RR = P(ingredient | flare) / P(ingredient | good).
    - RR > 1 → trigger candidate (more common before flares)
    - RR < 1 → safe candidate (more common before good days)
    - RR = ∞ when the ingredient is absent from good windows (undefined denominator — reported as ∞ by convention, sorted to top of trigger list)
    - RR = 0 when the ingredient is absent from flare windows

    No smoothing / correction. Zero cells are reported honestly.

    Only includes ingredients with ≥2 occurrences in at least one of the two
    groups — singletons are too noisy to interpret.
    """
    all_pairs = set(flare_freq) | set(good_freq)
    rows = []
    for pair in all_pairs:
        a = flare_freq.get(pair, 0)     # flares with ingredient
        c = good_freq.get(pair, 0)      # good days with ingredient
        if max(a, c) < 2:
            continue
        flare_rate = a / flare_n if flare_n > 0 else 0.0
        good_rate = c / good_n if good_n > 0 else 0.0
        if good_rate == 0 and flare_rate == 0:
            continue  # both zero, filter should have caught this but double check
        if good_rate == 0:
            rr = float("inf")
        else:
            rr = flare_rate / good_rate
        rows.append((pair, rr, a, c))

    def fmt_rr(rr):
        if rr == float("inf"):
            return "  ∞  "
        if rr == 0:
            return " 0.00"
        return f"{rr:>5.2f}"

    def print_table(title: str, rows_sorted):
        print("=" * 78)
        print(title)
        print(f"(n_flare={flare_n}, n_good={good_n}; ∞ = ingredient never seen in good-day windows)")
        print("-" * 78)
        print(f"  {'RR':>5}   {'flare':>7}   {'good':>5}   ingredient")
        for (name, parent), rr, a, c in rows_sorted:
            prov_str = f"  (via {parent})" if parent else ""
            print(f"  {fmt_rr(rr)}   {a:>3}/{flare_n:<3}   {c:>2}/{good_n:<2}   {name}{prov_str}")

    # For trigger list: sort by RR desc, then by flare count desc (so ∞ rows are ordered by a).
    triggers = sorted(rows, key=lambda r: (-r[1], -r[2]))[:top_k]
    print_table(f"Top {len(triggers)} TRIGGER candidates (ranked by RR descending)", triggers)
    print()
    # For safe list: sort by RR asc, then by good count desc (so 0 rows are ordered by c).
    safe = sorted(rows, key=lambda r: (r[1], -r[3]))[:top_k]
    print_table(f"Top {len(safe)} SAFE candidates (ranked by RR ascending)", safe)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--parse",
        action="store_true",
        help="run scripts/bulk_parse_meals.py first to populate any NULL parsed_ingredients",
    )
    ap.add_argument(
        "--confirmed-only",
        action="store_true",
        help="exclude 'likely' ingredients from resolution (default: include both confirmed and likely)",
    )
    ap.add_argument(
        "--good-days",
        action="store_true",
        help="also show good-day windows (severity ≤ --good-threshold) and a flare-vs-good diff view",
    )
    ap.add_argument(
        "--good-threshold",
        type=int,
        default=4,
        help="severity threshold for 'good day' anchors (default: 4)",
    )
    ap.add_argument(
        "--default-storage",
        choices=list(STORAGE_VALUES),
        default=None,
        help="treat meals with null storage_state as this value (e.g. refrigerated for pre-tracking-era data)",
    )
    ap.add_argument(
        "--output",
        type=str,
        default=str(ROOT / "docs" / "reports" / "flare_dump.txt"),
        help="also write the full dump to this file (default: docs/reports/flare_dump.txt). Pass '' to disable.",
    )
    args = ap.parse_args()
    use_likely = not args.confirmed_only

    # Tee to output file if requested
    tee_file = None
    if args.output:
        tee_path = Path(args.output)
        tee_path.parent.mkdir(parents=True, exist_ok=True)
        tee_file = open(tee_path, "w")

        class Tee:
            def __init__(self, *streams):
                self.streams = streams
            def write(self, s):
                for st in self.streams:
                    st.write(s)
            def flush(self):
                for st in self.streams:
                    st.flush()
        sys.stdout = Tee(sys.__stdout__, tee_file)

    if args.parse:
        print("Running bulk_parse_meals.py first…")
        print("=" * 78)
        old_argv = sys.argv
        sys.argv = [str(ROOT / "scripts" / "bulk_parse_meals.py")]
        try:
            runpy.run_path(str(ROOT / "scripts" / "bulk_parse_meals.py"), run_name="__main__")
        finally:
            sys.argv = old_argv
        print("=" * 78)
        print()

    db = Database(DB_PATH)
    rise, window = get_flare_config()
    win_min_h, win_max_h = FLARE_WINDOW_HOURS

    all_skin = db.list_log_entries(entry_type="flare")
    flares = _detect_flares(all_skin)
    flares.sort(key=lambda f: _parse_ts(f["timestamp"]))
    meals = db.list_log_entries(entry_type="meal")

    print(f"Flare detection: rise ≥ {rise} from previous {window} check(s) → {len(flares)} flare check(s)")
    print(f"Pre-anchor window: {win_min_h}-{win_max_h}h before each anchor")
    print(f"Times: Sydney local (Australia/Sydney)")
    print(f"Ingredients: {'confirmed + likely' if use_likely else 'confirmed only'}")
    if args.default_storage:
        print(f"Default storage for null entries: {args.default_storage}")
    if args.good_days:
        flare_ids = {f["id"] for f in flares}
        good_anchors = detect_good_days(all_skin, args.good_threshold, exclude_ids=flare_ids)
        print(f"Good-day threshold: severity ≤ {args.good_threshold} (excluding flare checks) → {len(good_anchors)} good check(s)")
    print("=" * 78)
    print()

    # Flares
    print("━━━ FLARES ━━━\n")
    flare_stats = analyze_windows(
        "FLARE", flares, meals, db, win_min_h, win_max_h, use_likely, args.default_storage,
    )

    # Good days (optional)
    good_stats = None
    if args.good_days:
        print("━━━ GOOD DAYS ━━━\n")
        good_stats = analyze_windows(
            "GOOD", good_anchors, meals, db, win_min_h, win_max_h, use_likely, args.default_storage,
        )

    # Aggregates
    print_freq_table(
        "Resolved ingredient frequency across flare windows",
        flare_stats["resolved_freq"], flare_stats["n_anchors"],
    )
    print()
    if good_stats:
        print_freq_table(
            "Resolved ingredient frequency across good-day windows",
            good_stats["resolved_freq"], good_stats["n_anchors"],
        )
        print()
        print_rr_view(
            flare_stats["resolved_freq"], good_stats["resolved_freq"],
            flare_stats["n_anchors"], good_stats["n_anchors"],
        )
        print()

    # Storage totals
    print("=" * 78)
    print("Storage state summary (totals across pre-flare meals)")
    print("-" * 78)
    total = sum(flare_stats["storage_across_windows"].values())
    for state, count in flare_stats["storage_across_windows"].most_common():
        pct = 100 * count / total if total else 0
        print(f"  {count:>3}  {pct:>5.1f}%   {state}")
    if good_stats:
        print()
        print("Storage state summary (totals across good-day meals)")
        print("-" * 78)
        total = sum(good_stats["storage_across_windows"].values())
        for state, count in good_stats["storage_across_windows"].most_common():
            pct = 100 * count / total if total else 0
            print(f"  {count:>3}  {pct:>5.1f}%   {state}")

    # Raw names — only printed for flare side (where aliasing matters most)
    print()
    print("=" * 78)
    print("Raw ingredient names from pre-flare meals (aliasing candidates)")
    print("-" * 78)
    sorted_raw = sorted(flare_stats["raw_freq"].items(), key=lambda kv: (-kv[1], kv[0]))
    for raw, count in sorted_raw:
        resolved = db.resolve_ingredient(raw)
        if len(resolved) == 1 and resolved[0][1] is None and resolved[0][0] == raw:
            marker = ""
        else:
            marker = "  →  " + ", ".join(
                f"{n}{' (via ' + p + ')' if p else ''}" for n, p in resolved
            )
        print(f"  {count:>3}  {raw}{marker}")


if __name__ == "__main__":
    main()
