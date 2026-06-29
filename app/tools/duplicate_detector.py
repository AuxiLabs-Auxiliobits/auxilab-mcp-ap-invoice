from sqlalchemy.orm import Session

from app.database.models import ProcessedInvoice
from app.schemas.invoice import InvoiceData
from app.services.fuzzy_match import FuzzyMatcher


class DuplicateDetector:

    def __init__(self, db: Session):
        self.db = db

    def check_duplicate(self, invoice: InvoiceData):

        invoices = self.db.query(
            ProcessedInvoice
        ).all()

        for old in invoices:

            # Exact Invoice Number

            if (
                old.invoice_number
                == invoice.invoice_number.value
            ):

                return {
                    "is_duplicate": True,
                    "match_type": "Exact Duplicate",
                    "matched_invoice": old.invoice_number,
                    "confidence": 1.0,
                }

            similarity = FuzzyMatcher.similarity(
                invoice.vendor_name.value,
                old.vendor_name,
            )

            if old.grand_total is None:
                continue

            difference = abs(
                invoice.grand_total.value
                - old.grand_total
            )

            percentage = (
                difference
                / old.grand_total
            ) * 100

            if similarity >= 85 and percentage <= 5:

                return {
                    "is_duplicate": True,
                    "match_type": "Near Duplicate",
                    "matched_invoice": old.invoice_number,
                    "vendor_similarity": similarity,
                    "amount_difference": round(
                        percentage,
                        2,
                    ),
                    "confidence": round(
                        similarity / 100,
                        2,
                    ),
                }

        return {
            "is_duplicate": False,
            "match_type": "Unique Invoice",
            "confidence": 1.0,
        }

    def save_invoice(self, invoice: InvoiceData):

        db_invoice = ProcessedInvoice(
            invoice_number=invoice.invoice_number.value,
            vendor_name=invoice.vendor_name.value,
            invoice_date=invoice.invoice_date.value,
            due_date=invoice.due_date.value,
            subtotal=invoice.subtotal.value,
            tax=invoice.tax.value,
            grand_total=invoice.grand_total.value,
            status="Processed",
        )

        self.db.add(db_invoice)

        self.db.commit()