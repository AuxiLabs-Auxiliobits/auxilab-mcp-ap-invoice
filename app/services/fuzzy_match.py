from rapidfuzz import fuzz


class FuzzyMatcher:
    """
    Utility class for fuzzy string matching.
    """

    @staticmethod
    def similarity(str1: str, str2: str) -> float:
        if not str1 or not str2:
            return 0.0

        return fuzz.token_sort_ratio(
            str1.lower(),
            str2.lower()
        )

    @staticmethod
    def is_match(str1: str, str2: str, threshold: int = 85) -> bool:
        return (
            FuzzyMatcher.similarity(str1, str2)
            >= threshold
        )