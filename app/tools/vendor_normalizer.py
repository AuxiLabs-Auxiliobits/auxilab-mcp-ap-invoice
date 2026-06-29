from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.config import VENDOR_NORMALIZER_MIN_MARGIN, VENDOR_NORMALIZER_THRESHOLD
from app.core.logging import get_logger
from app.repositories.vendor_repository import VendorRepository
from app.services.fuzzy_match import FuzzyMatcher
from app.tools.vendor_onboarding import VendorOnboarding


logger = get_logger(__name__)


@dataclass(slots=True)
class VendorMatch:
    vendor_name: str
    canonical_name: str
    email: str | None
    country: str | None
    raw_score: float
    normalized_score: float

    @property
    def score(self) -> float:
        return round((self.raw_score + self.normalized_score) / 2, 2)


class VendorNormalizer:
    def __init__(self, db: Session):
        self.db = db
        self.repository = VendorRepository(db)
        self.onboarding = VendorOnboarding(db)

    def _score(self, query: str, candidate: str) -> VendorMatch:
        normalized_query = FuzzyMatcher.normalize(query)
        normalized_candidate = FuzzyMatcher.normalize(candidate)

        raw_score = float(fuzz.WRatio(query.casefold(), candidate.casefold()))
        normalized_score = float(
            fuzz.token_set_ratio(normalized_query, normalized_candidate)
        )

        return VendorMatch(
            vendor_name=candidate,
            canonical_name=candidate,
            email=None,
            country=None,
            raw_score=raw_score,
            normalized_score=normalized_score,
        )

    def normalize(
        self,
        vendor_name: str,
        *,
        auto_queue_unknown: bool = True,
    ) -> dict[str, Any]:
        if not isinstance(vendor_name, str) or not vendor_name.strip():
            raise ValueError("vendor_name must be a non-empty string")

        normalized_input = FuzzyMatcher.normalize(vendor_name)
        vendors = self.repository.list_vendors()

        if not vendors:
            result = self._queue_if_needed(vendor_name, auto_queue_unknown)
            return {
                "recognized": False,
                "input_vendor": vendor_name,
                "canonical_vendor": None,
                "confidence": 0.0,
                "recommended_action": "Vendor Onboarding Required",
                "pending_vendor": result,
                "candidates": [],
            }

        candidates: list[VendorMatch] = []
        for vendor in vendors:
            candidate = self._score(vendor_name, vendor.vendor_name)
            candidate.canonical_name = vendor.canonical_name
            candidate.email = vendor.email
            candidate.country = vendor.country

            if FuzzyMatcher.normalize(vendor.vendor_name) == normalized_input:
                candidate.raw_score = 100.0
                candidate.normalized_score = 100.0

            candidates.append(candidate)

        exact_candidates = [
            candidate
            for candidate in candidates
            if FuzzyMatcher.normalize(candidate.vendor_name) == normalized_input
        ]
        if exact_candidates:
            exact_candidates.sort(
                key=lambda item: (
                    item.raw_score,
                    item.normalized_score,
                    -len(item.vendor_name),
                ),
                reverse=True,
            )
            best = max(
                exact_candidates,
                key=lambda item: (
                    item.raw_score,
                    item.normalized_score,
                    -len(item.vendor_name),
                ),
            )
            candidates.sort(key=lambda item: item.score, reverse=True)
            logger.info(
                "Vendor recognized by normalized exact match",
                extra={
                    "vendor_name": vendor_name,
                    "matched_vendor": best.vendor_name,
                    "confidence": best.score,
                },
            )
            return {
                "recognized": True,
                "input_vendor": vendor_name,
                "matched_vendor": best.vendor_name,
                "canonical_vendor": best.canonical_name,
                "email": best.email,
                "country": best.country,
                "confidence": 100.0,
                "recommended_action": "Use Canonical Vendor",
                "pending_vendor": None,
                "candidates": self._format_candidates(candidates[:3]),
            }

        candidates.sort(key=lambda item: item.score, reverse=True)
        best = candidates[0]
        runner_up = candidates[1].score if len(candidates) > 1 else 0.0
        margin = best.score - runner_up

        if (
            best.score < VENDOR_NORMALIZER_THRESHOLD
            or margin < VENDOR_NORMALIZER_MIN_MARGIN
        ):
            logger.info(
                "Vendor not confidently recognized",
                extra={
                    "vendor_name": vendor_name,
                    "best_score": best.score,
                    "margin": round(margin, 2),
                },
            )
            result = self._queue_if_needed(vendor_name, auto_queue_unknown)
            return {
                "recognized": False,
                "input_vendor": vendor_name,
                "canonical_vendor": None,
                "matched_vendor": None,
                "confidence": round(best.score, 2),
                "recommended_action": "Vendor Onboarding Required",
                "pending_vendor": result,
                "candidates": self._format_candidates(candidates[:3]),
            }

        logger.info(
            "Vendor recognized",
            extra={
                "vendor_name": vendor_name,
                "matched_vendor": best.vendor_name,
                "confidence": best.score,
            },
        )

        return {
            "recognized": True,
            "input_vendor": vendor_name,
            "matched_vendor": best.vendor_name,
            "canonical_vendor": best.canonical_name,
            "email": best.email,
            "country": best.country,
            "confidence": round(best.score, 2),
            "recommended_action": "Use Canonical Vendor",
            "pending_vendor": None,
            "candidates": self._format_candidates(candidates[:3]),
        }

    def _queue_if_needed(
        self,
        vendor_name: str,
        auto_queue_unknown: bool,
    ) -> dict[str, Any] | None:
        if not auto_queue_unknown:
            return None

        queued = self.onboarding.queue_vendor(vendor_name)
        return queued

    def _format_candidates(self, candidates: list[VendorMatch]) -> list[dict[str, Any]]:
        return [
            {
                "vendor_name": candidate.vendor_name,
                "canonical_name": candidate.canonical_name,
                "email": candidate.email,
                "country": candidate.country,
                "score": round(candidate.score, 2),
                "raw_score": round(candidate.raw_score, 2),
                "normalized_score": round(candidate.normalized_score, 2),
            }
            for candidate in candidates
        ]
