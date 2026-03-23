import json
import logging
from typing import Optional

import anthropic

from config import CLAUDE_MODEL
from prompts import TEXT_PARSING_PROMPT, IMAGE_PARSING_PROMPT

logger = logging.getLogger(__name__)

_client: Optional[anthropic.Anthropic] = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def parse_ingredients_from_text(meal_text: str) -> Optional[dict]:
    try:
        response = get_client().messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": TEXT_PARSING_PROMPT.format(meal_text=meal_text),
            }],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Failed to parse ingredients: {e}")
        return None


def parse_ingredients_from_image(image_path: str) -> Optional[dict]:
    import base64
    import mimetypes
    try:
        mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        with open(image_path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")
        response = get_client().messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}},
                    {"type": "text", "text": IMAGE_PARSING_PROMPT},
                ],
            }],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Failed to parse ingredients from image: {e}")
        return None


def process_image_entry(db, entry_id: int, image_path: str) -> None:
    entry = db.get_log_entry(entry_id)
    if not entry:
        return
    result = parse_ingredients_from_image(image_path)
    if result:
        # Merge with existing parsed ingredients if any
        existing = None
        if entry.get("parsed_ingredients"):
            try:
                existing = json.loads(entry["parsed_ingredients"])
            except json.JSONDecodeError:
                pass
        if existing:
            for key in ("confirmed", "likely"):
                merged = list(set(existing.get(key, []) + result.get(key, [])))
                result[key] = merged
        db.update_parse_result(entry_id, status="parsed", ingredients=json.dumps(result))


def process_pending_entry(db, entry_id: int) -> None:
    entry = db.get_log_entry(entry_id)
    if not entry or entry["parse_status"] != "pending":
        return

    result = parse_ingredients_from_text(entry["raw_input"])
    if result:
        db.update_parse_result(entry_id, status="parsed", ingredients=json.dumps(result))
    else:
        db.update_parse_result(entry_id, status="failed", ingredients=None)
