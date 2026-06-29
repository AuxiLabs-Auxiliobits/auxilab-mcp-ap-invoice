from __future__ import annotations

import re

from rapidfuzz import fuzz


class FuzzyMatcher:
    """Utility helpers for conservative fuzzy vendor matching."""

    LEGAL_SUFFIXES = {
        "ag",
        "bv",
        "co",
        "company",
        "corp",
        "corporation",
        "inc",
        "incorporated",
        "llc",
        "ltd",
        "limited",
        "plc",
        "pvt",
        "private",
        "se",
        "sarl",
        "sa",
        "gmbh",
    }

    @classmethod
    def normalize(cls, value: str) -> str:
        tokens = re.findall(r"[a-z0-9]+", value.casefold())
        filtered = [token for token in tokens if token not in cls.LEGAL_SUFFIXES]
        return " ".join(filtered)

    @classmethod
    def similarity(cls, str1: str, str2: str) -> float:
        if not str1 or not str2:
            return 0.0

        left = cls.normalize(str1)
        right = cls.normalize(str2)

        if not left or not right:
            return 0.0

        token_score = fuzz.token_set_ratio(left, right)
        ratio_score = fuzz.WRatio(left, right)
        return round((token_score * 0.6) + (ratio_score * 0.4), 2)

    @classmethod
    def is_match(cls, str1: str, str2: str, threshold: int = 90) -> bool:
        return cls.similarity(str1, str2) >= threshold
