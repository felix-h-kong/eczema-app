#!/usr/bin/env python3
"""Retroactive tagging: user's stated rule is that every home-made lentil stew
contains a Continental chicken stock pot unless explicitly declared otherwise.

This script finds lentil stew entries that don't mention vegetable stock / veg
stock / no stock, and adds 'continental chicken stock pot' to their confirmed
ingredients (if not already present).

By default, prints a dry-run preview. Pass --apply to actually update.

Usage:
    python scripts/retro_tag_stock_pot.py              # preview
    python scripts/retro_tag_stock_pot.py --apply      # actually update
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from db import Database
from config import DB_PATH

STOCK_POT_NAME = "continental chicken stock pot"
TRIGGER = "lentil stew"
EXCLUDE_PATTERNS = ("vegetable stock", "veg stock", "no stock", "no chicken stock")


def should_tag(raw_input: str) -> bool:
    if not raw_input:
        return False
    lower = raw_input.lower()
    if TRIGGER not in lower:
        return False
    if any(p in lower for p in EXCLUDE_PATTERNS):
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually update the DB (default: dry-run)")
    args = ap.parse_args()

    db = Database(DB_PATH)
    meals = db.list_log_entries(entry_type="meal")

    candidates = [m for m in meals if should_tag(m.get("raw_input") or "")]

    print(f"Found {len(candidates)} candidate lentil stew entries")
    print(f"  trigger: raw_input contains '{TRIGGER}'")
    print(f"  exclude: raw_input mentions {EXCLUDE_PATTERNS}")
    print("-" * 78)

    updates = []
    already_tagged = []
    for m in candidates:
        raw_pi = m.get("parsed_ingredients")
        if raw_pi:
            try:
                pi = json.loads(raw_pi)
            except (json.JSONDecodeError, TypeError):
                pi = {"confirmed": [], "likely": [], "source": "text"}
        else:
            pi = {"confirmed": [], "likely": [], "source": "text"}

        confirmed = [c.strip() for c in pi.get("confirmed", [])]
        if any(STOCK_POT_NAME.lower() == c.lower() for c in confirmed):
            already_tagged.append(m)
        else:
            confirmed.append(STOCK_POT_NAME)
            pi["confirmed"] = confirmed
            updates.append((m, json.dumps(pi)))

    for m in already_tagged:
        print(f"  ALREADY TAGGED  id={m['id']}  {m['timestamp'][:10]}  \"{(m.get('raw_input') or '')[:70]}\"")
    for m, _ in updates:
        print(f"  WILL UPDATE     id={m['id']}  {m['timestamp'][:10]}  \"{(m.get('raw_input') or '')[:70]}\"")

    print("-" * 78)
    print(f"Summary: {len(already_tagged)} already tagged, {len(updates)} to update.")

    if not args.apply:
        print()
        print("Dry-run only. Re-run with --apply to actually update the DB.")
        return

    for m, payload in updates:
        db.update_parse_result(m["id"], status="parsed", ingredients=payload)
    print(f"Updated {len(updates)} entries.")


if __name__ == "__main__":
    main()
