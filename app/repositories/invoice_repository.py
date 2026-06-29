from __future__ import annotations

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

