from __future__ import annotations

import re
from typing import Any


_CURRENCY_RE = re.compile(r"[,$£€₹]")


def coerce_float(value: Any, *, allow_percent: bool = False) -> float | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return float(int(value))

    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        raise ValueError(f"Unsupported numeric value type: {type(value).__name__}")

    cleaned = value.strip()
    if not cleaned:
        return None

    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1].strip()}"

    if allow_percent and cleaned.endswith("%"):
        cleaned = cleaned[:-1].strip()

    cleaned = _CURRENCY_RE.sub("", cleaned)
    cleaned = cleaned.replace(" ", "")

    if allow_percent and cleaned.endswith("%"):
        cleaned = cleaned[:-1].strip()

    if not cleaned:
        return None

    return float(cleaned)
