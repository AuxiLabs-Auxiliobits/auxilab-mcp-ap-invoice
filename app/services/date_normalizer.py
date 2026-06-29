from __future__ import annotations

from datetime import date, datetime

from dateutil import parser

from app.core.errors import AppError, app_error


class DateNormalizer:
    SUPPORTED_FORMATS = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%b %d %Y",
        "%B %d %Y",
    ]

    @classmethod
    def parse(cls, value: str) -> date:
        if not isinstance(value, str) or not value.strip():
            raise app_error(
                "VALIDATION_ERROR",
                "Date value must be a non-empty string.",
                step="normalize_dates",
            )

        candidate = value.strip()
        for date_format in cls.SUPPORTED_FORMATS:
            try:
                return datetime.strptime(candidate, date_format).date()
            except ValueError:
                continue

        try:
            if "/" in candidate:
                parts = [segment for segment in candidate.split("/") if segment]
                if len(parts) == 3 and all(part.isdigit() for part in parts):
                    first, second, _ = [int(part) for part in parts]
                    if first > 12:
                        return parser.parse(candidate, dayfirst=True).date()
                    if second > 12:
                        return parser.parse(candidate, dayfirst=False).date()
                    return parser.parse(candidate, dayfirst=False).date()

            return parser.parse(candidate, dayfirst=False).date()
        except (ValueError, OverflowError, parser.ParserError) as exc:
            raise app_error(
                "VALIDATION_ERROR",
                f"Unsupported date format: {value}",
                step="normalize_dates",
                details={"raw_value": value},
            ) from exc

    @classmethod
    def to_iso8601(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            value = str(value)
        if not value.strip():
            return None
        return cls.parse(value).isoformat()

