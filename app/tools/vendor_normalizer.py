from rapidfuzz import process, fuzz
from sqlalchemy.orm import Session

from app.database.models import Vendor


class VendorNormalizer:

    def __init__(self, db: Session):
        self.db = db

    def normalize(self, vendor_name: str):

        vendors = self.db.query(Vendor).all()

        choices = {}

        for vendor in vendors:
            choices[vendor.vendor_name] = vendor

        result = process.extractOne(
            vendor_name,
            choices.keys(),
            scorer=fuzz.WRatio
        )

        if result is None:
            return {
                "recognized": False,
                "input_vendor": vendor_name,
                "canonical_vendor": None,
                "confidence": 0,
                "recommended_action": "Vendor Onboarding Required"
            }

        matched_name, score, _ = result

        vendor = choices[matched_name]

        if score < 60:
            return {
                "recognized": False,
                "input_vendor": vendor_name,
                "canonical_vendor": None,
                "confidence": round(score, 2),
                "recommended_action": "Vendor Onboarding Required"
            }

        return {
            "recognized": True,
            "input_vendor": vendor_name,
            "matched_vendor": matched_name,
            "canonical_vendor": vendor.canonical_name,
            "email": vendor.email,
            "country": vendor.country,
            "confidence": round(score, 2)
        }