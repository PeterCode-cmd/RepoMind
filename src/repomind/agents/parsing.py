"""Parsing helpers for model responses.

Models are asked for a single JSON object, but they sometimes wrap it in code
fences or add prose. These helpers keep the agent layer tolerant without ever
trusting the content: callers validate every field they use.
"""

from __future__ import annotations

import json
from typing import Any


def parse_json_object(raw: str) -> dict[str, Any] | None:
    """Parse a JSON object from a model response, tolerating code fences.

    Returns ``None`` when the response is not a JSON object.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return None
    return document if isinstance(document, dict) else None


def string_tuple(value: object) -> tuple[str, ...]:
    """Return the non-empty strings of a model field, or an empty tuple."""
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
