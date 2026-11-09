"""Small, dependency-free helpers shared across engines and API layers."""
from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import date, datetime, timezone
from typing import Any


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:64] or "project"


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_date(value: Any) -> str | None:
    parsed = parse_datetime(value)
    return parsed.date().isoformat() if parsed else None


def canonical(value: Any) -> str:
    """Normalise values for deterministic contradiction detection."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"\b(the|a|an|is|was|will be|has been)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return value
