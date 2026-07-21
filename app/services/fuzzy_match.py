from __future__ import annotations

import re

from rapidfuzz import fuzz


class FuzzyMatcher:
    """
    Utility class for fuzzy string matching.
    """

    @staticmethod
    def normalize(value: str) -> str:
        if not isinstance(value, str):
            return ""

        cleaned = value.casefold().strip()
        cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    @staticmethod
    def similarity(str1: str, str2: str) -> float:
        if not str1 or not str2:
            return 0.0

        return fuzz.token_sort_ratio(FuzzyMatcher.normalize(str1), FuzzyMatcher.normalize(str2))

    @staticmethod
    def is_match(str1: str, str2: str, threshold: int = 85) -> bool:
        return (
            FuzzyMatcher.similarity(str1, str2)
            >= threshold
        )
