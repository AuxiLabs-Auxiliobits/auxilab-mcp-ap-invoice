from __future__ import annotations

from time import perf_counter
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import DEFAULT_PAYMENT_TERMS
from app.core.errors import AppError, app_error, map_exception_to_error
from app.core.logging import get_logger
from app.core.responses import error_response, step_result
from app.schemas.tool_requests import InvoiceToolRequest
from app.services.gemini_service import GeminiService
from app.services.invoice_inputs import InvoiceInputResolver, ResolvedInvoiceInput
from app.services.number_parser import coerce_float
from app.tools.completeness_checker import CompletenessChecker
from app.tools.duplicate_detector import DuplicateDetector
from app.tools.payment_terms import PaymentTermsCalculator
from app.tools.vendor_normalizer import VendorNormalizer
from app.tools.vendor_onboarding import VendorOnboarding


logger = get_logger(__name__)


class InvoiceProcessor:
    def __init__(self, db: Session):
        self.db = db
        self.gemini = GeminiService()
        self.detector = DuplicateDetector(db)
        self.normalizer = VendorNormalizer(db)
        self.onboarding = VendorOnboarding(db)
        self.completeness_checker = CompletenessChecker()
        self.payment_terms_calculator = PaymentTermsCalculator()
        self.resolver = InvoiceInputResolver()

    def build_request(
        self,
        source: Any = None,
        *,
        pdf_path: str | None = None,
        uploaded_file: Any = None,
        text: str | None = None,
        invoice_json: Any = None,
        url: str | None = None,
        base64_data: str | None = None,
        raw_bytes: bytes | list[int] | None = None,
    ) -> InvoiceToolRequest:
        return InvoiceToolRequest(
            source=source,
            pdf_path=pdf_path,
            uploaded_file=uploaded_file,
            text=text,
            invoice_json=invoice_json,
            url=url,
            base64_data=base64_data,
            raw_bytes=raw_bytes,
        )

    def resolve_input(self, request: InvoiceToolRequest) -> ResolvedInvoiceInput:
        return self.resolver.resolve(
            request.source,
            pdf_path=request.pdf_path,
            uploaded_file=request.uploaded_file,
            text=request.text,
            invoice_json=request.invoice_json,
            url=request.url,
            base64_data=request.base64_data,
            raw_bytes=request.raw_bytes,
        )

    def extract(
        self,
        source: Any = None,
        *,
        pdf_path: str | None = None,
        uploaded_file: Any = None,
        text: str | None = None,
        invoice_json: Any = None,
        url: str | None = None,
        base64_data: str | None = None,
        raw_bytes: bytes | list[int] | None = None,
    ) -> Any:
        request = self.build_request(
            source,
            pdf_path=pdf_path,
            uploaded_file=uploaded_file,
            text=text,
            invoice_json=invoice_json,
            url=url,
            base64_data=base64_data,
            raw_bytes=raw_bytes,
        )
        resolved = self.resolve_input(request)
        try:
            return self.gemini.extract_from_resolved(resolved)
        finally:
            resolved.cleanup()

    def extract_with_details(
        self,
        source: Any = None,
        *,
        pdf_path: str | None = None,
        uploaded_file: Any = None,
        text: str | None = None,
        invoice_json: Any = None,
        url: str | None = None,
        base64_data: str | None = None,
        raw_bytes: bytes | list[int] | None = None,
    ) -> dict[str, Any]:
        request = self.build_request(
            source,
            pdf_path=pdf_path,
            uploaded_file=uploaded_file,
            text=text,
            invoice_json=invoice_json,
            url=url,
            base64_data=base64_data,
            raw_bytes=raw_bytes,
        )
        resolved = self.resolve_input(request)
        try:
            invoice = self.gemini.extract_from_resolved(resolved)
            return {
                "invoice": invoice,
                "resolved": resolved,
            }
        finally:
            resolved.cleanup()

    def process(
        self,
        source: Any = None,
        *,
        pdf_path: str | None = None,
        uploaded_file: Any = None,
        text: str | None = None,
        invoice_json: Any = None,
        url: str | None = None,
        base64_data: str | None = None,
        raw_bytes: bytes | list[int] | None = None,
        payment_terms: str | None = None,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        steps: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        resolved: ResolvedInvoiceInput | None = None
        invoice = None

        logger.info("Starting invoice processing pipeline")

        try:
            request = self.build_request(
                source,
                pdf_path=pdf_path,
                uploaded_file=uploaded_file,
                text=text,
                invoice_json=invoice_json,
                url=url,
                base64_data=base64_data,
                raw_bytes=raw_bytes,
            )
        except (ValidationError, ValueError) as exc:
            logger.exception("Invoice request validation failed")
            return error_response(step="resolve_input", error=exc)

        try:
            resolved = self.resolve_input(request)
            steps.append(
                step_result(
                    step="resolve_input",
                    status="ok",
                    message="Invoice input resolved.",
                    data=self._resolved_summary(resolved),
                )
            )
        except Exception as exc:  # noqa: BLE001
            mapped = map_exception_to_error(exc, step="resolve_input")
            logger.exception("Failed to resolve invoice input")
            steps.append(
                step_result(
                    step="resolve_input",
                    status="error",
                    message=mapped.message,
                    error=mapped,
                )
            )
            return {
                "ok": False,
                "status": "error",
                "step": "process_invoice",
                "error_code": mapped.error_code,
                "message": mapped.message,
                "details": mapped.details,
                "steps": steps,
                "errors": [self._error_payload(mapped, "resolve_input")],
                "processing_duration_ms": round((perf_counter() - started_at) * 1000, 2),
            }

        try:
            invoice = self.gemini.extract_from_resolved(resolved)
            steps.append(
                step_result(
                    step="extract_invoice",
                    status="ok",
                    message="Invoice extracted successfully.",
                )
            )
        except Exception as exc:  # noqa: BLE001
            mapped = map_exception_to_error(exc, step="extract_invoice")
            logger.exception("Invoice extraction failed")
            steps.append(
                step_result(
                    step="extract_invoice",
                    status="error",
                    message=mapped.message,
                    error=mapped,
                )
            )
            return {
                "ok": False,
                "status": "error",
                "step": "process_invoice",
                "error_code": mapped.error_code,
                "message": mapped.message,
                "details": mapped.details,
                "input": self._resolved_summary(resolved),
                "steps": steps,
                "errors": [self._error_payload(mapped, "extract_invoice")],
                "processing_duration_ms": round((perf_counter() - started_at) * 1000, 2),
            }
        finally:
            if resolved is not None:
                resolved.cleanup()

        vendor_result: dict[str, Any] | None = None
        duplicate_result: dict[str, Any] | None = None
        payment_terms_result: dict[str, Any] | None = None
        completeness_result: dict[str, Any] | None = None
        pending_vendor_result: dict[str, Any] | None = None
        save_result: dict[str, Any] | None = None

        vendor_name = str(invoice.vendor_name.value or "").strip()
        if vendor_name:
            try:
                vendor_result = self.normalizer.normalize(
                    vendor_name,
                    auto_queue_unknown=True,
                )
                steps.append(
                    step_result(
                        step="normalize_vendor",
                        status="ok",
                        message="Vendor normalization completed.",
                        data=vendor_result,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                mapped = map_exception_to_error(exc, step="normalize_vendor")
                logger.exception("Vendor normalization failed")
                vendor_result = {
                    "recognized": False,
                    "input_vendor": vendor_name,
                    "canonical_vendor": None,
                    "confidence": 0.0,
                    "recommended_action": "Vendor Onboarding Required",
                }
                errors.append(self._error_payload(mapped, "normalize_vendor"))
                steps.append(
                    step_result(
                        step="normalize_vendor",
                        status="error",
                        message=mapped.message,
                        data=vendor_result,
                        error=mapped,
                    )
                )
        else:
            mapped = app_error(
                "VALIDATION_ERROR",
                "Extracted invoice did not contain a vendor name.",
                step="normalize_vendor",
            )
            vendor_result = {
                "recognized": False,
                "input_vendor": None,
                "canonical_vendor": None,
                "confidence": 0.0,
                "recommended_action": "Vendor Onboarding Required",
            }
            errors.append(self._error_payload(mapped, "normalize_vendor"))
            steps.append(
                step_result(
                    step="normalize_vendor",
                    status="error",
                    message=mapped.message,
                    data=vendor_result,
                    error=mapped,
                )
            )

        try:
            duplicate_result = self.detector.check_duplicate(invoice)
            steps.append(
                step_result(
                    step="detect_duplicate",
                    status="ok",
                    message="Duplicate detection completed.",
                    data=duplicate_result,
                )
            )
        except Exception as exc:  # noqa: BLE001
            mapped = map_exception_to_error(exc, step="detect_duplicate")
            logger.exception("Duplicate detection failed")
            duplicate_result = {
                "is_duplicate": False,
                "match_type": "Unknown",
                "confidence": 0.0,
            }
            errors.append(self._error_payload(mapped, "detect_duplicate"))
            steps.append(
                step_result(
                    step="detect_duplicate",
                    status="error",
                    message=mapped.message,
                    data=duplicate_result,
                    error=mapped,
                )
            )

        terms = (
            str(invoice.payment_terms.value).strip()
            if invoice.payment_terms.value not in (None, "")
            else (payment_terms or DEFAULT_PAYMENT_TERMS)
        )
        invoice_date = str(invoice.invoice_date.value or "").strip()
        amount = coerce_float(invoice.grand_total.value)

        if invoice_date and amount is not None:
            try:
                payment_terms_result = self.payment_terms_calculator.calculate(
                    invoice_date=invoice_date,
                    payment_terms=terms,
                    invoice_amount=amount,
                )
                steps.append(
                    step_result(
                        step="calculate_payment_terms",
                        status="ok",
                        message="Payment terms calculated.",
                        data=payment_terms_result,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                mapped = map_exception_to_error(exc, step="calculate_payment_terms")
                logger.exception("Payment terms calculation failed")
                payment_terms_result = {
                    "payment_terms": terms,
                    "error": mapped.message,
                }
                errors.append(self._error_payload(mapped, "calculate_payment_terms"))
                steps.append(
                    step_result(
                        step="calculate_payment_terms",
                        status="error",
                        message=mapped.message,
                        data=payment_terms_result,
                        error=mapped,
                    )
                )
        else:
            mapped = app_error(
                "VALIDATION_ERROR",
                "Missing invoice date or grand total.",
                step="calculate_payment_terms",
            )
            payment_terms_result = {
                "payment_terms": terms,
                "error": mapped.message,
            }
            errors.append(self._error_payload(mapped, "calculate_payment_terms"))
            steps.append(
                step_result(
                    step="calculate_payment_terms",
                    status="error",
                    message=mapped.message,
                    data=payment_terms_result,
                    error=mapped,
                )
            )

        try:
            completeness_result = self.completeness_checker.check(invoice)
            steps.append(
                step_result(
                    step="check_completeness",
                    status="ok",
                    message="Completeness check completed.",
                    data=completeness_result,
                )
            )
        except Exception as exc:  # noqa: BLE001
            mapped = map_exception_to_error(exc, step="check_completeness")
            logger.exception("Completeness check failed")
            completeness_result = {
                "completeness_score": 0.0,
                "missing_fields": [],
                "recommended_action": "Return to Vendor",
            }
            errors.append(self._error_payload(mapped, "check_completeness"))
            steps.append(
                step_result(
                    step="check_completeness",
                    status="error",
                    message=mapped.message,
                    data=completeness_result,
                    error=mapped,
                )
            )

        if vendor_result and not vendor_result.get("recognized") and vendor_name:
            pending_vendor_result = vendor_result.get("pending_vendor")
            if pending_vendor_result is not None:
                steps.append(
                    step_result(
                        step="queue_unknown_vendor",
                        status="ok",
                        message="Unknown vendor queued during normalization.",
                        data=pending_vendor_result,
                    )
                )
            else:
                try:
                    pending_vendor_result = self.onboarding.queue_vendor(vendor_name)
                    steps.append(
                        step_result(
                            step="queue_unknown_vendor",
                            status="ok",
                            message="Unknown vendor queued for approval.",
                            data=pending_vendor_result,
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    mapped = map_exception_to_error(exc, step="queue_unknown_vendor")
                    logger.exception("Pending vendor queue failed")
                    errors.append(self._error_payload(mapped, "queue_unknown_vendor"))
                    steps.append(
                        step_result(
                            step="queue_unknown_vendor",
                            status="error",
                            message=mapped.message,
                            error=mapped,
                        )
                    )

        if duplicate_result and duplicate_result.get("is_duplicate", False):
            save_result = {
                "saved": False,
                "reason": "duplicate_invoice",
            }
            steps.append(
                step_result(
                    step="save_invoice",
                    status="skipped",
                    message="Invoice was not saved because it appears to be a duplicate.",
                    data=save_result,
                )
            )
        else:
            try:
                persisted_vendor_name = (
                    vendor_result.get("canonical_vendor")
                    if vendor_result and vendor_result.get("recognized")
                    else None
                )
                save_result = self.detector.save_invoice(
                    invoice,
                    vendor_name=persisted_vendor_name,
                )
                steps.append(
                    step_result(
                        step="save_invoice",
                        status="ok",
                        message="Invoice saved.",
                        data=save_result,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                mapped = map_exception_to_error(exc, step="save_invoice")
                logger.exception("Invoice save failed")
                save_result = {
                    "saved": False,
                    "error": mapped.message,
                }
                errors.append(self._error_payload(mapped, "save_invoice"))
                steps.append(
                    step_result(
                        step="save_invoice",
                        status="error",
                        message=mapped.message,
                        data=save_result,
                        error=mapped,
                    )
                )

        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.info(
            "Invoice processing finished",
            extra={
                "processing_duration_ms": duration_ms,
                "error_count": len(errors),
            },
        )

        return {
            "ok": True,
            "status": "completed" if not errors else "completed_with_errors",
            "input": self._resolved_summary(resolved),
            "invoice": invoice.model_dump(),
            "vendor": vendor_result,
            "duplicate": duplicate_result,
            "payment_terms": payment_terms_result,
            "completeness": completeness_result,
            "pending_vendor": pending_vendor_result,
            "save_result": save_result,
            "steps": steps,
            "errors": errors,
            "processing_duration_ms": duration_ms,
        }

    def _resolved_summary(self, resolved: ResolvedInvoiceInput | None) -> dict[str, Any] | None:
        if resolved is None:
            return None

        return {
            "kind": resolved.kind,
            "source_label": resolved.source_label,
            "detected_input_type": resolved.detected_input_type,
            "filename": resolved.filename,
            "mime_type": resolved.mime_type,
            "url": resolved.url,
            "details": resolved.details,
        }

    def _error_payload(self, error: AppError, step: str) -> dict[str, Any]:
        mapped = map_exception_to_error(error, step=step)
        return {
            "step": step,
            "error_code": mapped.error_code,
            "message": mapped.message,
            "details": mapped.details,
        }

