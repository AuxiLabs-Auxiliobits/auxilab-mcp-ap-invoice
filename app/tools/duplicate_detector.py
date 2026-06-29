from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import (
    DEFAULT_DUPLICATE_AMOUNT_VARIANCE_PERCENT,
    DEFAULT_DUPLICATE_DATE_WINDOW_DAYS,
    DEFAULT_DUPLICATE_VENDOR_THRESHOLD,
)
from app.core.logging import get_logger
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.invoice import InvoiceData
from app.services.fuzzy_match import FuzzyMatcher
from app.tools.payment_terms import PaymentTermsCalculator


logger = get_logger(__name__)


class DuplicateDetector:
    def __init__(self, db: Session):
        self.db = db
        self.repository = InvoiceRepository(db)

    def _coerce_invoice(
        self,
        invoice: InvoiceData | None = None,
        *,
        invoice_number: str | None = None,
        vendor_name: str | None = None,
        amount: float | None = None,
        invoice_date: str | None = None,
        due_date: str | None = None,
        subtotal: float | None = None,
        tax: float | None = None,
        grand_total: float | None = None,
    ) -> InvoiceData:
        if invoice is not None:
            if any(
                value is not None
                for value in (
                    invoice_number,
                    vendor_name,
                    amount,
                    invoice_date,
                    due_date,
                    subtotal,
                    tax,
                    grand_total,
                )
            ):
                resolved_total = grand_total if grand_total is not None else amount
                payload = invoice.model_dump()
                if invoice_number is not None:
                    payload["invoice_number"]["value"] = invoice_number
                if vendor_name is not None:
                    payload["vendor_name"]["value"] = vendor_name
                if invoice_date is not None:
                    payload["invoice_date"]["value"] = invoice_date
                if due_date is not None:
                    payload["due_date"]["value"] = due_date
                if subtotal is not None:
                    payload["subtotal"]["value"] = subtotal
                if tax is not None:
                    payload["tax"]["value"] = tax
                if resolved_total is not None:
                    payload["grand_total"]["value"] = resolved_total
                return InvoiceData.model_validate(payload)
            return invoice

        if not invoice_number:
            raise ValueError("invoice_number is required")
        if not vendor_name:
            raise ValueError("vendor_name is required")

        resolved_total = grand_total if grand_total is not None else amount
        if resolved_total is None:
            raise ValueError("grand_total or amount is required")

        def _field(value: Any, confidence: float = 1.0) -> dict[str, Any]:
            return {
                "value": value,
                "confidence": confidence if value not in (None, "") else 0.0,
            }

        return InvoiceData.model_validate(
            {
                "invoice_number": _field(invoice_number),
                "vendor_name": _field(vendor_name),
                "invoice_date": _field(invoice_date),
                "due_date": _field(due_date),
                "subtotal": _field(subtotal),
                "tax": _field(tax),
                "grand_total": _field(resolved_total),
                "line_items": [],
            }
        )

    def check_duplicate(
        self,
        invoice: InvoiceData | None = None,
        *,
        invoice_number: str | None = None,
        vendor_name: str | None = None,
        amount: float | None = None,
        invoice_date: str | None = None,
        due_date: str | None = None,
        subtotal: float | None = None,
        tax: float | None = None,
        grand_total: float | None = None,
    ) -> dict[str, Any]:
        invoice = self._coerce_invoice(
            invoice,
            invoice_number=invoice_number,
            vendor_name=vendor_name,
            amount=amount,
            invoice_date=invoice_date,
            due_date=due_date,
            subtotal=subtotal,
            tax=tax,
            grand_total=grand_total,
        )

        invoices = self.repository.list_processed_invoices()
        parsed_invoice_date = None
        if invoice.invoice_date.value:
            try:
                parsed_invoice_date = PaymentTermsCalculator().parse_date(
                    str(invoice.invoice_date.value)
                )
            except ValueError:
                parsed_invoice_date = None

        for old in invoices:
            if old.invoice_number and old.invoice_number.casefold().strip() == str(invoice.invoice_number.value).casefold().strip():
                return {
                    "is_duplicate": True,
                    "match_type": "Exact Duplicate",
                    "matched_invoice": old.invoice_number,
                    "confidence": 1.0,
                }

            if (
                not old.vendor_name
                or old.grand_total is None
                or invoice.grand_total.value is None
            ):
                continue

            similarity = FuzzyMatcher.similarity(
                str(invoice.vendor_name.value or ""),
                old.vendor_name,
            )

            if similarity < DEFAULT_DUPLICATE_VENDOR_THRESHOLD:
                continue

            try:
                difference = abs(
                    float(invoice.grand_total.value) - float(old.grand_total)
                )
            except (TypeError, ValueError):
                continue

            if float(old.grand_total) == 0:
                continue

            percentage = (difference / float(old.grand_total)) * 100
            if percentage > DEFAULT_DUPLICATE_AMOUNT_VARIANCE_PERCENT:
                continue

            if parsed_invoice_date and old.invoice_date:
                try:
                    old_invoice_date = PaymentTermsCalculator().parse_date(
                        str(old.invoice_date)
                    )
                    date_delta = abs((parsed_invoice_date - old_invoice_date).days)
                    if date_delta > DEFAULT_DUPLICATE_DATE_WINDOW_DAYS:
                        continue
                except ValueError:
                    pass

            return {
                "is_duplicate": True,
                "match_type": "Near Duplicate",
                "matched_invoice": old.invoice_number,
                "vendor_similarity": round(similarity, 2),
                "amount_difference": round(percentage, 2),
                "confidence": round(min(1.0, similarity / 100), 2),
            }

        return {
            "is_duplicate": False,
            "match_type": "Unique Invoice",
            "confidence": 1.0,
        }

    def save_invoice(
        self,
        invoice: InvoiceData | None = None,
        *,
        invoice_number: str | None = None,
        vendor_name: str | None = None,
        amount: float | None = None,
        invoice_date: str | None = None,
        due_date: str | None = None,
        subtotal: float | None = None,
        tax: float | None = None,
        grand_total: float | None = None,
        status: str = "Processed",
    ) -> dict[str, Any]:
        invoice = self._coerce_invoice(
            invoice,
            invoice_number=invoice_number,
            vendor_name=vendor_name,
            amount=amount,
            invoice_date=invoice_date,
            due_date=due_date,
            subtotal=subtotal,
            tax=tax,
            grand_total=grand_total,
        )

        try:
            saved = self.repository.save_invoice(
                invoice_number=str(invoice.invoice_number.value),
                vendor_name=str(invoice.vendor_name.value),
                invoice_date=str(invoice.invoice_date.value)
                if invoice.invoice_date.value is not None
                else None,
                due_date=str(invoice.due_date.value)
                if invoice.due_date.value is not None
                else None,
                subtotal=float(invoice.subtotal.value)
                if invoice.subtotal.value is not None
                else None,
                tax=float(invoice.tax.value) if invoice.tax.value is not None else None,
                grand_total=float(invoice.grand_total.value)
                if invoice.grand_total.value is not None
                else None,
                status=status,
            )
            self.db.commit()
            return {
                "saved": True,
                "invoice_id": saved.id,
                "invoice_number": saved.invoice_number,
                "vendor_name": saved.vendor_name,
                "status": saved.status,
            }
        except SQLAlchemyError:
            self.db.rollback()
            logger.exception("Failed to save invoice")
            raise
