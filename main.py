from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger
from app.core.responses import error_response, success_response
from app.database.bootstrap import initialize_database
from app.database.database import SessionLocal
from app.services.invoice_processor import InvoiceProcessor
from app.services.number_parser import coerce_float
from app.tools.completeness_checker import CompletenessChecker
from app.tools.duplicate_detector import DuplicateDetector
from app.tools.payment_terms import PaymentTermsCalculator
from app.tools.vendor_normalizer import VendorNormalizer
from app.tools.vendor_onboarding import VendorOnboarding


logger = get_logger(__name__)
initialize_database()

mcp = FastMCP(
    name="AP Invoice Intelligence MCP Server",
    instructions="""
AP Invoice Intelligence MCP Server

Supported invoice inputs:
- local file path
- Linux/macOS file path
- file:// URI
- uploaded file payloads
- base64 PDF or image
- raw PDF or image bytes
- HTTP/HTTPS URL
- invoice text
- invoice JSON

Available Tools:
1. extract_invoice
2. normalize_vendor
3. detect_duplicate
4. calculate_payment_terms
5. check_completeness
6. process_invoice
7. list_pending_vendors
8. approve_vendor
9. reject_vendor
""".strip(),
)


@contextmanager
def db_session() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _tool_error(step: str, exc: Exception) -> dict[str, Any]:
    logger.exception("Tool execution failed", extra={"step": step})
    return error_response(step=step, error=exc)


@mcp.tool()
def extract_invoice(
    source: Any = None,
    pdf_path: str | None = None,
    uploaded_file: Any = None,
    text: str | None = None,
    invoice_json: Any = None,
    url: str | None = None,
    base64_data: str | None = None,
    raw_bytes: bytes | list[int] | None = None,
) -> dict[str, Any]:
    """Extract invoice fields from a path, upload payload, URL, base64 data, text, or JSON."""

    with db_session() as db:
        try:
            processor = InvoiceProcessor(db)
            result = processor.extract_with_details(
                source,
                pdf_path=pdf_path,
                uploaded_file=uploaded_file,
                text=text,
                invoice_json=invoice_json,
                url=url,
                base64_data=base64_data,
                raw_bytes=raw_bytes,
            )
            return success_response(
                step="extract_invoice",
                data=result["invoice"].model_dump(),
                input=processor._resolved_summary(result["resolved"]),
            )
        except (FileNotFoundError, ValidationError, ValueError, SQLAlchemyError) as exc:
            return _tool_error("extract_invoice", exc)
        except Exception as exc:  # noqa: BLE001
            return _tool_error("extract_invoice", exc)


@mcp.tool()
def normalize_vendor(
    vendor_name: str,
    auto_queue_unknown: bool = True,
) -> dict[str, Any]:
    """Normalize a vendor name conservatively and optionally queue unknown vendors."""

    with db_session() as db:
        try:
            normalizer = VendorNormalizer(db)
            return success_response(
                step="normalize_vendor",
                data=normalizer.normalize(
                    vendor_name,
                    auto_queue_unknown=auto_queue_unknown,
                ),
            )
        except (ValueError, SQLAlchemyError) as exc:
            return _tool_error("normalize_vendor", exc)


@mcp.tool()
def detect_duplicate(
    invoice_number: str,
    vendor_name: str,
    amount: float,
    invoice_date: str,
) -> dict[str, Any]:
    """Check whether an invoice appears to be a duplicate."""

    with db_session() as db:
        try:
            detector = DuplicateDetector(db)
            result = detector.check_duplicate(
                invoice_number=invoice_number,
                vendor_name=vendor_name,
                amount=amount,
                invoice_date=invoice_date,
            )
            return success_response(step="detect_duplicate", data=result)
        except (ValueError, SQLAlchemyError) as exc:
            return _tool_error("detect_duplicate", exc)


@mcp.tool()
def calculate_payment_terms(
    invoice_date: str,
    payment_terms: str,
    invoice_amount: float,
) -> dict[str, Any]:
    """Calculate due dates and early-payment discounts for invoice terms."""

    try:
        calculator = PaymentTermsCalculator()
        result = calculator.calculate(
            invoice_date,
            payment_terms,
            coerce_float(invoice_amount) if invoice_amount is not None else invoice_amount,
        )
        return success_response(step="calculate_payment_terms", data=result)
    except ValueError as exc:
        return _tool_error("calculate_payment_terms", exc)


@mcp.tool()
def check_completeness(
    source: Any = None,
    pdf_path: str | None = None,
    uploaded_file: Any = None,
    text: str | None = None,
    invoice_json: Any = None,
    url: str | None = None,
    base64_data: str | None = None,
    raw_bytes: bytes | list[int] | None = None,
) -> dict[str, Any]:
    """Check whether a provided invoice payload is complete enough to process."""

    with db_session() as db:
        try:
            processor = InvoiceProcessor(db)
            result = processor.extract_with_details(
                source,
                pdf_path=pdf_path,
                uploaded_file=uploaded_file,
                text=text,
                invoice_json=invoice_json,
                url=url,
                base64_data=base64_data,
                raw_bytes=raw_bytes,
            )
            checker = CompletenessChecker()
            return success_response(
                step="check_completeness",
                data=checker.check(result["invoice"]),
                input=processor._resolved_summary(result["resolved"]),
            )
        except (FileNotFoundError, ValidationError, ValueError, SQLAlchemyError) as exc:
            return _tool_error("check_completeness", exc)
        except Exception as exc:  # noqa: BLE001
            return _tool_error("check_completeness", exc)


@mcp.tool()
def process_invoice(
    source: Any = None,
    pdf_path: str | None = None,
    uploaded_file: Any = None,
    text: str | None = None,
    invoice_json: Any = None,
    url: str | None = None,
    base64_data: str | None = None,
    raw_bytes: bytes | list[int] | None = None,
    payment_terms: str | None = None,
) -> dict[str, Any]:
    """Run the full AP invoice pipeline with resilient step-by-step results."""

    with db_session() as db:
        try:
            processor = InvoiceProcessor(db)
            return processor.process(
                source,
                pdf_path=pdf_path,
                uploaded_file=uploaded_file,
                text=text,
                invoice_json=invoice_json,
                url=url,
                base64_data=base64_data,
                raw_bytes=raw_bytes,
                payment_terms=payment_terms,
            )
        except (FileNotFoundError, ValidationError, ValueError, SQLAlchemyError) as exc:
            return _tool_error("process_invoice", exc)
        except Exception as exc:  # noqa: BLE001
            return _tool_error("process_invoice", exc)


@mcp.tool()
def list_pending_vendors() -> dict[str, Any]:
    """List vendors currently awaiting approval."""

    with db_session() as db:
        try:
            onboarding = VendorOnboarding(db)
            return success_response(
                step="list_pending_vendors",
                data=onboarding.list_pending(),
            )
        except SQLAlchemyError as exc:
            return _tool_error("list_pending_vendors", exc)


@mcp.tool()
def approve_vendor(
    vendor_id: int,
    confirm: bool,
) -> dict[str, Any]:
    """Approve a pending vendor and move it into vendor master."""

    with db_session() as db:
        try:
            onboarding = VendorOnboarding(db)
            return success_response(
                step="approve_vendor",
                data=onboarding.approve(vendor_id, confirm),
            )
        except (ValueError, SQLAlchemyError) as exc:
            return _tool_error("approve_vendor", exc)


@mcp.tool()
def reject_vendor(
    vendor_id: int,
    confirm: bool,
) -> dict[str, Any]:
    """Reject and remove a pending vendor."""

    with db_session() as db:
        try:
            onboarding = VendorOnboarding(db)
            return success_response(
                step="reject_vendor",
                data=onboarding.reject(vendor_id, confirm),
            )
        except (ValueError, SQLAlchemyError) as exc:
            return _tool_error("reject_vendor", exc)


if __name__ == "__main__":
    mcp.run(transport="stdio")
