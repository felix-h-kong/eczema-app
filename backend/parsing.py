import json
import logging
from typing import Optional

import anthropic

from config import CLAUDE_MODEL
from prompts import TEXT_PARSING_PROMPT

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


def process_pending_entry(db, entry_id: int) -> None:
    entry = db.get_log_entry(entry_id)
    if not entry or entry["parse_status"] != "pending":
        return

    result = parse_ingredients_from_text(entry["raw_input"])
    if result:
        db.update_parse_result(entry_id, status="parsed", ingredients=json.dumps(result))
    else:
        db.update_parse_result(entry_id, status="failed", ingredients=None)
