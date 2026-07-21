from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models import ProcessedInvoice


def normalize_invoice_key(value: str) -> str:
    return " ".join(value.casefold().split())


class InvoiceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_invoice_number(self, invoice_number: str) -> ProcessedInvoice | None:
        key = normalize_invoice_key(invoice_number)
        return (
            self.db.query(ProcessedInvoice)
            .filter(func.lower(func.trim(ProcessedInvoice.invoice_number)) == key)
            .first()
        )

    def list_processed_invoices(self) -> list[ProcessedInvoice]:
        return (
            self.db.query(ProcessedInvoice)
            .order_by(ProcessedInvoice.id.asc())
            .all()
        )

    def save_invoice(
        self,
        *,
        invoice_number: str,
        vendor_name: str,
        invoice_date: str | None,
        due_date: str | None,
        subtotal: float | None,
        tax: float | None,
        discount_percentage: float | None = None,
        discount_amount: float | None = None,
        shipping_charges: float | None = None,
        freight_charges: float | None = None,
        handling_charges: float | None = None,
        insurance_charges: float | None = None,
        packaging_charges: float | None = None,
        other_charges: list[dict[str, Any]] | None = None,
        grand_total: float | None,
        status: str = "Processed",
    ) -> ProcessedInvoice:
        existing = self.get_by_invoice_number(invoice_number)
        if existing is not None:
            return existing

        invoice = ProcessedInvoice(
            invoice_number=invoice_number.strip(),
            vendor_name=vendor_name.strip(),
            invoice_date=invoice_date,
            due_date=due_date,
            subtotal=subtotal,
            tax=tax,
            discount_percentage=discount_percentage,
            discount_amount=discount_amount,
            shipping_charges=shipping_charges,
            freight_charges=freight_charges,
            handling_charges=handling_charges,
            insurance_charges=insurance_charges,
            packaging_charges=packaging_charges,
            other_charges_json=(
                json.dumps(other_charges, ensure_ascii=False)
                if other_charges is not None
                else None
            ),
            grand_total=grand_total,
            status=status,
        )

        try:
            self.db.add(invoice)
            self.db.flush()
            return invoice
        except SQLAlchemyError:
            self.db.rollback()
            raise
