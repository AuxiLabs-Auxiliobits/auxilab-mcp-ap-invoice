from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from dateutil import parser as date_parser

from app.schemas.invoice import ConfidenceField, InvoiceData
from app.services.pdf_parser import PDFParser
from app.tools.payment_terms import PaymentTermsCalculator


class LocalInvoiceExtractor:
    """
    Extracts invoice fields from selectable PDF text without any LLM.
    """

    _DATE_PATTERNS = (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%m.%d.%Y",
        "%d %b %Y",
        "%b %d %Y",
        "%d %B %Y",
        "%B %d %Y",
    )

    _MONEY_PATTERN = re.compile(
        r"(?P<currency>[$€£₹]|USD|EUR|GBP|INR)?\s*"
        r"(?P<amount>-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|-?\d+(?:\.\d{1,2})?)",
        re.IGNORECASE,
    )

    _LABEL_VALUE_PATTERNS = {
        "invoice_number": (
            r"\binvoice\s*(?:number|no\.?|#|id)?\b[:\-\s]*"
            r"(?P<value>[A-Z0-9][A-Z0-9\-\/_.]+)",
            r"\binv\.?\s*(?:no\.?|#)\b[:\-\s]*"
            r"(?P<value>[A-Z0-9][A-Z0-9\-\/_.]+)",
        ),
        "invoice_date": (
            r"\binvoice\s*date\b[:\-\s]*(?P<value>.+)$",
            r"\bdate\b[:\-\s]*(?P<value>.+)$",
        ),
        "due_date": (
            r"\bdue\s*date\b[:\-\s]*(?P<value>.+)$",
            r"\bpayment\s*due\b[:\-\s]*(?P<value>.+)$",
        ),
        "po_number": (
            r"\b(?:po|p\.o\.|purchase\s*order)\s*(?:number|no\.?|#|id)?\b[:\-\s]*"
            r"(?P<value>[A-Z0-9][A-Z0-9\-\/_.]+)",
        ),
        "payment_terms": (
            r"\bpayment\s*terms\b[:\-\s]*(?P<value>.+)$",
            r"\bterms\b[:\-\s]*(?P<value>.+)$",
        ),
    }

    _LABEL_KEYWORDS = (
        "invoice",
        "date",
        "due",
        "subtotal",
        "total",
        "tax",
        "amount",
        "bill to",
        "ship to",
        "purchase order",
        "po number",
        "payment terms",
        "page",
        "statement",
        "remit",
        "customer",
    )

    _VENDOR_STOPWORDS = (
        "invoice",
        "date",
        "due",
        "subtotal",
        "total",
        "tax",
        "bill to",
        "ship to",
        "purchase order",
        "po",
        "payment terms",
        "page",
        "remit",
        "statement",
        "invoice number",
    )

    def __init__(self) -> None:
        self.payment_terms_calculator = PaymentTermsCalculator()
        self.last_metadata: dict[str, str | None] = {}

    def extract_invoice(self, input_path: str) -> InvoiceData:
        text = PDFParser.extract_text(input_path)
        return self.extract_from_text(text)

    def extract_from_text(self, text: str) -> InvoiceData:
        lines = self._clean_lines(text)

        invoice_number = self._extract_invoice_number(lines, text)
        vendor_name = self._extract_vendor_name(lines)
        invoice_date = self._extract_date_field(lines, text, "invoice_date")
        po_number = self._extract_label_value(lines, text, "po_number")
        currency = self._extract_currency(lines, text)
        payment_terms = self._extract_payment_terms(lines, text)
        due_date = self._extract_date_field(lines, text, "due_date")
        subtotal = self._extract_amount(lines, ("subtotal",))
        tax = self._extract_amount(lines, ("tax",))
        grand_total = self._extract_grand_total(lines)

        self.last_metadata = {
            "po_number": po_number,
            "currency": currency,
            "payment_terms": payment_terms,
        }

        if due_date is None and payment_terms and invoice_date:
            due_date = self._derive_due_date(invoice_date, payment_terms, subtotal, grand_total)

        return InvoiceData(
            invoice_number=self._confidence_field(invoice_number),
            vendor_name=self._confidence_field(vendor_name),
            invoice_date=self._confidence_field(invoice_date),
            due_date=self._confidence_field(due_date),
            subtotal=self._confidence_field(subtotal),
            tax=self._confidence_field(tax),
            grand_total=self._confidence_field(grand_total),
        )

    def _clean_lines(self, text: str) -> list[str]:
        return [
            re.sub(r"\s+", " ", line).strip()
            for line in text.splitlines()
            if line and line.strip()
        ]

    def _confidence_field(self, value):
        return ConfidenceField(
            value=value,
            confidence=0.0 if value is None else 0.95,
        )

    def _extract_invoice_number(self, lines: list[str], text: str) -> str | None:
        value = self._extract_label_value(lines, text, "invoice_number")
        if value:
            return value

        for line in lines[:12]:
            if self._looks_like_invoice_number(line):
                return line.strip(" :#-")

        return None

    def _extract_vendor_name(self, lines: list[str]) -> str | None:
        if not lines:
            return None

        best_match: tuple[int, str] | None = None

        for index, line in enumerate(lines[:12]):
            score = self._vendor_score(line, index)
            if score <= 0:
                continue

            if best_match is None or score > best_match[0]:
                best_match = (score, line)

        return best_match[1] if best_match else None

    def _extract_payment_terms(self, lines: list[str], text: str) -> str | None:
        value = self._extract_label_value(lines, text, "payment_terms")
        if value:
            return value

        patterns = (
            r"\bnet\s*\d+\b",
            r"\b\d+/\d+\s+net\s+\d+\b",
            r"\bdue\s+on\s+receipt\b",
        )

        for source in (lines, [text]):
            for item in source:
                for pattern in patterns:
                    match = re.search(pattern, item, re.IGNORECASE)
                    if match:
                        return match.group(0).strip()

        return None

    def _extract_currency(self, lines: list[str], text: str) -> str | None:
        label_patterns = (
            r"\bcurrency\b[:\-\s]*(?P<value>[A-Z]{3}|[$€£₹])",
            r"\bcurr\.?\b[:\-\s]*(?P<value>[A-Z]{3}|[$€£₹])",
        )

        value = self._extract_first_match(lines, text, label_patterns)
        if value:
            return self._normalize_currency(value)

        for source in (lines, [text]):
            for item in source:
                match = re.search(r"[$€£₹]", item)
                if match:
                    return self._normalize_currency(match.group(0))

                match = re.search(r"\b(USD|EUR|GBP|INR)\b", item, re.IGNORECASE)
                if match:
                    return match.group(1).upper()

        return None

    def _extract_date_field(
        self,
        lines: list[str],
        text: str,
        field_name: str,
    ) -> str | None:
        value = self._extract_label_value(lines, text, field_name)
        if value:
            parsed = self._parse_date(value)
            if parsed:
                return parsed

        return None

    def _extract_amount(self, lines: list[str], labels: Iterable[str]) -> float | None:
        for label in labels:
            for line in lines:
                if not re.search(rf"\b{re.escape(label)}\b", line, re.IGNORECASE):
                    continue

                amount = self._parse_money(line)
                if amount is not None:
                    return amount

                trailing_value = line.split(":", 1)[-1].strip()
                amount = self._parse_money(trailing_value)
                if amount is not None:
                    return amount

        return None

    def _extract_grand_total(self, lines: list[str]) -> float | None:
        patterns = (
            r"\bgrand\s+total\b[:\-\s]*(?P<value>.+)$",
            r"\bamount\s+due\b[:\-\s]*(?P<value>.+)$",
            r"\bbalance\s+due\b[:\-\s]*(?P<value>.+)$",
            r"\binvoice\s+total\b[:\-\s]*(?P<value>.+)$",
            r"\btotal\s+due\b[:\-\s]*(?P<value>.+)$",
        )

        value = self._extract_numeric_label_value(lines, patterns)
        if value is not None:
            return value

        for line in reversed(lines[-8:]):
            if re.search(r"\btotal\b", line, re.IGNORECASE) and not re.search(
                r"\bsubtotal\b", line, re.IGNORECASE
            ):
                amount = self._parse_money(line)
                if amount is not None:
                    return amount

        return None

    def _extract_label_value(self, lines: list[str], text: str, field_name: str) -> str | None:
        patterns = self._LABEL_VALUE_PATTERNS.get(field_name, ())

        return self._extract_first_match(lines, text, patterns, field_name)

    def _extract_first_match(
        self,
        lines: list[str],
        text: str,
        patterns: Iterable[str],
        field_name: str | None = None,
    ) -> str | None:

        for source in (lines, [text]):
            for item in source:
                for pattern in patterns:
                    match = re.search(pattern, item, re.IGNORECASE | re.MULTILINE)
                    if match:
                        value = match.group("value").strip()
                        if field_name in {"invoice_date", "due_date"}:
                            return self._first_date_like_value(value)
                        return self._trim_field_value(value)

        return None

    def _extract_numeric_label_value(
        self,
        lines: list[str],
        patterns: Iterable[str],
    ) -> float | None:
        for source in lines:
            for pattern in patterns:
                match = re.search(pattern, source, re.IGNORECASE)
                if not match:
                    continue

                amount = self._parse_money(match.group("value"))
                if amount is not None:
                    return amount

                amount = self._parse_money(source)
                if amount is not None:
                    return amount

        return None

    def _parse_money(self, value: str) -> float | None:
        match = self._MONEY_PATTERN.search(value.replace(",", ""))
        if not match:
            return None

        try:
            return float(match.group("amount").replace(",", ""))
        except ValueError:
            return None

    def _parse_date(self, value: str) -> str | None:
        candidate = self._first_date_like_value(value)
        if candidate is None:
            return None

        for fmt in self._DATE_PATTERNS:
            try:
                return datetime.strptime(candidate, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue

        try:
            parsed = date_parser.parse(candidate, dayfirst=False, fuzzy=True)
        except (ValueError, TypeError):
            return None

        return parsed.strftime("%Y-%m-%d")

    def _first_date_like_value(self, value: str) -> str | None:
        match = re.search(
            r"(\d{4}-\d{2}-\d{2}"
            r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
            r"|\d{1,2}\.\d{1,2}\.\d{2,4}"
            r"|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}"
            r"|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4})",
            value,
        )
        return match.group(1).strip() if match else None

    def _trim_field_value(self, value: str) -> str:
        value = value.strip().strip(" :,-")
        value = re.sub(r"\s+", " ", value)
        return value

    def _normalize_currency(self, value: str) -> str | None:
        value = value.strip()

        return {
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
            "₹": "INR",
        }.get(value, value.upper() if value else None)

    def _looks_like_invoice_number(self, line: str) -> bool:
        if len(line) < 4:
            return False

        if any(self._contains_term(line, keyword) for keyword in self._LABEL_KEYWORDS):
            return False

        return bool(re.search(r"[A-Z0-9]{4,}", line))

    def _vendor_score(self, line: str, index: int) -> int:
        lower = line.lower()

        if any(self._contains_term(line, keyword) for keyword in self._VENDOR_STOPWORDS):
            return -10

        if not re.search(r"[A-Za-z]", line):
            return -10

        score = 0

        if index == 0:
            score += 4
        elif index < 3:
            score += 2

        word_count = len(line.split())
        if 2 <= word_count <= 8:
            score += 3

        if re.search(r"\b(inc|inc\.|llc|ltd|limited|corp|corporation|company|co\.|plc|se)\b", lower):
            score += 3

        if not re.search(r"\d", line):
            score += 2

        if len(line) > 60:
            score -= 2

        return score

    def _contains_term(self, text: str, term: str) -> bool:
        return bool(re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE))

    def _derive_due_date(
        self,
        invoice_date: str,
        payment_terms: str,
        subtotal: float | None,
        grand_total: float | None,
    ) -> str | None:
        invoice_amount = grand_total if grand_total is not None else subtotal or 0.0

        try:
            result = self.payment_terms_calculator.calculate(
                invoice_date=invoice_date,
                payment_terms=payment_terms,
                invoice_amount=float(invoice_amount),
            )
        except Exception:
            return None

        return result.get("due_date")
