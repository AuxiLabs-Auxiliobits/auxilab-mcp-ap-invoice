from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any

from app.core.logging import get_logger
from app.services.date_normalizer import DateNormalizer


logger = get_logger(__name__)


class PaymentTermsCalculator:
    SUPPORTED_DATE_FORMATS = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]

    def parse_date(self, date_str: str) -> datetime:
        normalized = DateNormalizer.to_iso8601(date_str)
        if normalized is None:
            raise ValueError("invoice_date must be a non-empty string")
        return datetime.strptime(normalized, "%Y-%m-%d")

    def calculate(
        self,
        invoice_date: str,
        payment_terms: str,
        invoice_amount: float,
    ) -> dict[str, Any]:
        parsed_invoice_date = self.parse_date(invoice_date)

        if not isinstance(payment_terms, str) or not payment_terms.strip():
            raise ValueError("payment_terms must be a non-empty string")

        payment_terms = payment_terms.strip()
        invoice_amount = float(invoice_amount)

        if payment_terms.casefold() == "due on receipt":
            due_date = parsed_invoice_date
            return {
                "payment_terms": payment_terms,
                "due_date": due_date.strftime("%Y-%m-%d"),
                "discount_deadline": None,
                "discount_amount": 0.0,
                "days_until_due": 0,
            }

        match = re.fullmatch(r"Net\s+(\d+)", payment_terms, re.IGNORECASE)
        if match:
            days = int(match.group(1))
            due_date = parsed_invoice_date + timedelta(days=days)
            return {
                "payment_terms": payment_terms,
                "due_date": due_date.strftime("%Y-%m-%d"),
                "discount_deadline": None,
                "discount_amount": 0.0,
                "days_until_due": days,
            }

        match = re.fullmatch(
            r"(\d+)\/(\d+)\s+Net\s+(\d+)",
            payment_terms,
            re.IGNORECASE,
        )
        if match:
            discount_percent = float(match.group(1))
            discount_days = int(match.group(2))
            due_days = int(match.group(3))

            due_date = parsed_invoice_date + timedelta(days=due_days)
            discount_deadline = parsed_invoice_date + timedelta(days=discount_days)
            discount_amount = round(invoice_amount * (discount_percent / 100), 2)

            return {
                "payment_terms": payment_terms,
                "due_date": due_date.strftime("%Y-%m-%d"),
                "discount_deadline": discount_deadline.strftime("%Y-%m-%d"),
                "discount_amount": discount_amount,
                "days_until_due": due_days,
                "days_until_discount": discount_days,
            }

        logger.warning("Unsupported payment terms", extra={"payment_terms": payment_terms})
        return {
            "payment_terms": payment_terms,
            "error": "Unsupported payment terms",
        }
