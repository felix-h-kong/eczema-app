#!/usr/bin/env python3
"""Bulk-parse meal log entries using Claude Opus 4.6.

Finds all meal entries with NULL parsed_ingredients (text-only, never parsed)
and runs a single chunked LLM pass to fill them in. Uses prompt caching on the
shared system prompt.

Usage:
    python scripts/bulk_parse_meals.py                 # parse all unparsed
    python scripts/bulk_parse_meals.py --limit 5       # parse first 5 (testing)
    python scripts/bulk_parse_meals.py --force         # re-parse everything
    python scripts/bulk_parse_meals.py --chunk-size 30 # smaller batches
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / "backend" / ".env")

import anthropic
from db import Database
from config import DB_PATH

MODEL = "claude-opus-4-6"
DEFAULT_CHUNK_SIZE = 50

SYSTEM_PROMPT = """You are extracting food ingredients and storage state from meal log entries for a self-experimentation eczema tracking app (histamine intolerance is one of the hypotheses). For each entry, return ingredient names and a storage classification.

For each entry, return:
- "confirmed": ingredients explicitly mentioned in the text
- "likely": ingredients that are typical constituents of the described dishes but not explicitly stated
- "storage_state": one of the values listed below, or null

Ingredient rules:
- Prefer individual ingredients over dish names. For regional/compound dishes (e.g. "wat tan hor", "bun bo hue", "pad thai"), list their typical component ingredients in "likely" (e.g. for wat tan hor: rice noodles, egg, prawns, char siu pork, soy sauce, oyster sauce, bean sprouts).
- Use lowercase.
- If a specific packaged product or brand name is mentioned (e.g. "Continental chicken stock pot", "Weet-Bix", "Vegemite", "Tim Tam"), keep the full product name in "confirmed" — a separate system handles decomposition into component ingredients. Do NOT decompose packaged products yourself.
- If a meal text is vague ("snack", "drink", "something at the cafe"), return only what is explicitly stated in "confirmed"; leave "likely" empty. Do not guess.
- Beverages: list their ingredients (e.g. "hot black tea" → confirmed: ["black tea", "water"], likely: []; "flat white" → confirmed: ["espresso", "milk"], likely: []; "negroni" → confirmed: ["gin", "campari", "sweet vermouth"], likely: []).
- If the text is not about food at all (e.g. just a timestamp or an unrelated note), return empty arrays for both.

Storage state — pick exactly one, or null if not applicable / unclear:
- "fresh": cooked/assembled and eaten the same day with no meaningful storage (e.g. toast, a freshly made stir-fry, a smoothie just blended).
- "restaurant": ordered/served from a restaurant, café, or food court — storage state is not the user's responsibility and typically fresh.
- "refrigerated": the meal was stored in a fridge before eating (leftovers, overnight or multi-day meal prep, fridge pasta). Include overnight fridge storage in this category.
- "frozen": the meal was frozen and then reheated (frozen meal-prep batches, commercial frozen meals).
- "room_temp": the meal was knowingly left unrefrigerated for hours before eating (unusual — only if the user says so).
- "shelf_stable": packaged snacks, biscuits, chocolate, dried fruit, cereals, chips, soft drinks — products designed to sit at room temperature.
- null: the storage state is not stated, not inferable, or the concept doesn't apply (raw fruit eaten on the spot, coffee, water, a sip of something, etc.).

Storage cues in text — examples:
- "refrigerated immediately", "fridge", "leftover", "day 3 of pasta" → refrigerated
- "frozen batch", "reheated from the freezer" → frozen
- "at [restaurant name]", "Papparich", "cafe" → restaurant
- "fresh", "just made", "homemade [same-day cooking mentioned]" → fresh
- Tim Tam, Weet-Bix, chips, chocolate, biscuits → shelf_stable
- If the text mentions both a cook event and a later eating event with fridge in between → refrigerated, regardless of how fresh the cooking was

Return a JSON array with one object per input entry:
[{"id": <id>, "confirmed": [...], "likely": [...], "storage_state": "refrigerated"|"fresh"|"restaurant"|"frozen"|"room_temp"|"shelf_stable"|null}, ...]

The order of objects must match the order of input entries, and every input id must be represented. Return ONLY the JSON array. No preamble, no markdown fences, no trailing text."""


def build_user_prompt(chunk: list[dict]) -> str:
    """Build the user message containing the numbered entry list."""
    lines = [f"Parse the following {len(chunk)} meal entries. Return a JSON array as specified."]
    lines.append("")
    for entry in chunk:
        # Clamp raw_input length to avoid one massive entry blowing the budget
        text = (entry.get("raw_input") or "").strip().replace("\n", " ")[:500]
        lines.append(f'  id={entry["id"]}: "{text}"')
    lines.append("")
    lines.append("Output the JSON array now.")
    return "\n".join(lines)


def extract_json_array(text: str) -> list[dict]:
    """Strip common wrappers and parse. Raises on failure."""
    text = text.strip()
    if text.startswith("```"):
        # Remove leading fence (possibly with lang) and trailing fence
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    return json.loads(text)


def parse_chunk(client: anthropic.Anthropic, chunk: list[dict]) -> dict[int, dict]:
    """Call Claude once for a chunk. Returns {entry_id: {"confirmed": [...], "likely": [...]}}."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": build_user_prompt(chunk)}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    parsed = extract_json_array(text)
    if not isinstance(parsed, list):
        raise ValueError(f"expected JSON array, got {type(parsed).__name__}")

    valid_storage = {"fresh", "restaurant", "refrigerated", "frozen", "room_temp", "shelf_stable"}
    by_id: dict[int, dict] = {}
    for item in parsed:
        if not isinstance(item, dict) or "id" not in item:
            continue
        raw_storage = item.get("storage_state")
        storage = raw_storage if raw_storage in valid_storage else None
        by_id[int(item["id"])] = {
            "confirmed": [str(x).strip() for x in item.get("confirmed", []) if str(x).strip()],
            "likely": [str(x).strip() for x in item.get("likely", []) if str(x).strip()],
            "storage_state": storage,
        }

    usage = response.usage
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
    print(
        f"    usage: input={usage.input_tokens} output={usage.output_tokens} "
        f"cache_read={cache_read} cache_create={cache_create}"
    )
    return by_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="parse only first N entries")
    ap.add_argument("--force", action="store_true", help="re-parse entries that already have parsed_ingredients")
    ap.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    ap.add_argument("--dry-run", action="store_true", help="print plan without calling API")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    db = Database(DB_PATH)

    all_meals = db.list_log_entries(entry_type="meal")
    if args.force:
        target = [m for m in all_meals if (m.get("raw_input") or "").strip()]
    else:
        target = [
            m for m in all_meals
            if not m.get("parsed_ingredients") and (m.get("raw_input") or "").strip()
        ]

    target.sort(key=lambda m: m["id"])

    if args.limit is not None:
        target = target[: args.limit]

    if not target:
        print("No entries to parse.")
        return

    n = len(target)
    chunks = [target[i : i + args.chunk_size] for i in range(0, n, args.chunk_size)]
    print(f"Parsing {n} entries in {len(chunks)} chunk(s) of up to {args.chunk_size} with model={MODEL}")

    if args.dry_run:
        for i, c in enumerate(chunks, 1):
            print(f"  chunk {i}/{len(chunks)}: {len(c)} entries, ids {c[0]['id']}..{c[-1]['id']}")
        return

    client = anthropic.Anthropic()
    total_parsed = 0
    total_skipped = 0
    for i, chunk in enumerate(chunks, 1):
        print(f"[chunk {i}/{len(chunks)}] parsing {len(chunk)} entries (ids {chunk[0]['id']}..{chunk[-1]['id']})…")
        try:
            by_id = parse_chunk(client, chunk)
        except Exception as e:
            print(f"    ✗ chunk failed: {e}", file=sys.stderr)
            total_skipped += len(chunk)
            continue

        parsed_in_chunk = 0
        skipped_in_chunk = 0
        for entry in chunk:
            result = by_id.get(entry["id"])
            if result is None:
                skipped_in_chunk += 1
                continue
            payload = json.dumps({
                "confirmed": result["confirmed"],
                "likely": result["likely"],
                "storage_state": result["storage_state"],
                "source": "text",
            })
            db.update_parse_result(entry["id"], status="parsed", ingredients=payload)
            parsed_in_chunk += 1
        total_parsed += parsed_in_chunk
        total_skipped += skipped_in_chunk
        print(f"    ✓ {parsed_in_chunk} parsed, {skipped_in_chunk} missing in model output")

    print()
    print(f"Done. Parsed {total_parsed}/{n}. Skipped {total_skipped}.")


if __name__ == "__main__":
    main()
