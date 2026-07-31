from mcp.server.fastmcp import FastMCP

from app.database.database import SessionLocal
from app.database.seed import seed_vendors
from app.services.invoice_processor import InvoiceProcessor
from app.tools.vendor_normalizer import VendorNormalizer
from app.tools.duplicate_detector import DuplicateDetector
from app.tools.payment_terms import PaymentTermsCalculator
from app.tools.completeness_checker import CompletenessChecker
from app.schemas.invoice import InvoiceData, ConfidenceField


seed_vendors()


mcp = FastMCP(
    name="AP Invoice Intelligence MCP Server",
    instructions="""
AP Invoice Intelligence MCP Server

Available Tools:
1. extract_invoice
2. normalize_vendor
3. detect_duplicate
4. calculate_payment_terms
5. check_completeness
"""
)


# ==========================================================
# Invoice Extraction
# ==========================================================

@mcp.tool()
def extract_invoice(pdf_path: str):
    """
    Extract invoice information from a PDF or image.
    """

    db = SessionLocal()

    try:
        processor = InvoiceProcessor(db)
        return processor.process(pdf_path)

    finally:
        db.close()


# ==========================================================
# Vendor Normalizer
# ==========================================================

@mcp.tool()
def normalize_vendor(vendor_name: str):
    """
    Normalize vendor names using the vendor master.
    """

    db = SessionLocal()

    try:
        normalizer = VendorNormalizer(db)
        return normalizer.normalize(vendor_name)

    finally:
        db.close()


# ==========================================================
# Duplicate Detector
# ==========================================================

@mcp.tool()
def detect_duplicate(
    invoice_number: str,
    vendor_name: str,
    amount: float,
    invoice_date: str,
):
    """
    Detect duplicate invoices.
    """

    db = SessionLocal()

    try:

        detector = DuplicateDetector(db)

        invoice = InvoiceData(
            invoice_number=ConfidenceField(
                value=invoice_number,
                confidence=1.0,
            ),
            vendor_name=ConfidenceField(
                value=vendor_name,
                confidence=1.0,
            ),
            invoice_date=ConfidenceField(
                value=invoice_date,
                confidence=1.0,
            ),
            due_date=ConfidenceField(
                value=None,
                confidence=0.0,
            ),
            subtotal=ConfidenceField(
                value=None,
                confidence=0.0,
            ),
            tax=ConfidenceField(
                value=None,
                confidence=0.0,
            ),
            grand_total=ConfidenceField(
                value=amount,
                confidence=1.0,
            ),
            line_items=[],
        )

        return detector.check_duplicate(invoice)

    finally:
        db.close()


# ==========================================================
# Payment Terms Calculator
# ==========================================================

@mcp.tool()
def calculate_payment_terms(
    invoice_date: str,
    payment_terms: str,
    invoice_amount: float,
):
    """
    Calculate payment due date and discounts.
    """

    calculator = PaymentTermsCalculator()

    return calculator.calculate(
        invoice_date,
        payment_terms,
        invoice_amount,
    )


# ==========================================================
# Completeness Checker
# ==========================================================

@mcp.tool()
def check_completeness(pdf_path: str):
    """
    Check invoice completeness.
    """

    db = SessionLocal()

    try:

        processor = InvoiceProcessor(db)

        invoice = processor.gemini.extract_invoice(pdf_path)

        checker = CompletenessChecker()

        return checker.check(invoice)

    finally:
        db.close()


# ==========================================================
# Run MCP Server
# ==========================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")
