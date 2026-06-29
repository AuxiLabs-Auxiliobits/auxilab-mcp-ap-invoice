from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, MODEL_NAME
from app.core.errors import app_error
from app.core.logging import get_logger
from app.schemas.invoice import InvoiceData
from app.services.invoice_inputs import InvoiceInputResolver, ResolvedInvoiceInput
from app.services.pdf_parser import PDFParser


logger = get_logger(__name__)


class GeminiService:
    def __init__(self) -> None:
        self._client: genai.Client | None = None
        self._resolver = InvoiceInputResolver()

    def _get_client(self) -> genai.Client:
        if self._client is not None:
            return self._client

        if not GEMINI_API_KEY:
            raise app_error(
                "GEMINI_ERROR",
                "GEMINI_API_KEY is not configured. Gemini extraction is unavailable.",
                step="extract_invoice",
            )

        self._client = genai.Client(api_key=GEMINI_API_KEY)
        return self._client

    def _invoice_prompt(self) -> str:
        return """
You are an Accounts Payable Invoice Extraction AI.

Extract every invoice field accurately.

Rules:

- Never invent values.
- Return null if unavailable.
- Confidence between 0 and 1.
- Return only valid JSON.

Return this schema:
{
  "invoice_number": {"value": "", "confidence": 0.0},
  "vendor_name": {"value": "", "confidence": 0.0},
  "invoice_date": {"value": "", "confidence": 0.0},
  "due_date": {"value": "", "confidence": 0.0},
  "subtotal": {"value": 0, "confidence": 0.0},
  "tax": {"value": 0, "confidence": 0.0},
  "grand_total": {"value": 0, "confidence": 0.0},
  "discount": {"value": 0, "confidence": 0.0},
  "shipping": {"value": 0, "confidence": 0.0},
  "balance_due": {"value": 0, "confidence": 0.0},
  "purchase_order": {"value": "", "confidence": 0.0},
  "order_id": {"value": "", "confidence": 0.0},
  "currency": {"value": "", "confidence": 0.0},
  "payment_terms": {"value": "", "confidence": 0.0},
  "bill_to": {"value": "", "confidence": 0.0},
  "ship_to": {"value": "", "confidence": 0.0},
  "invoice_type": {"value": "", "confidence": 0.0},
  "line_items": [
    {
      "description": {"value": "", "confidence": 0.0},
      "quantity": {"value": 0, "confidence": 0.0},
      "unit_price": {"value": 0, "confidence": 0.0},
      "total": {"value": 0, "confidence": 0.0}
    }
  ]
}
""".strip()

    def _parse_invoice_payload(self, payload: Any) -> InvoiceData:
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump()
        return InvoiceData.from_payload(payload)

    def _extract_json_from_text(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json").strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start : end + 1]
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed

        raise app_error(
            "VALIDATION_ERROR",
            "Gemini response did not contain valid JSON.",
            step="extract_invoice",
        )

    def extract_from_text(self, text: str) -> InvoiceData:
        if not isinstance(text, str) or not text.strip():
            raise app_error(
                "EMPTY_DOCUMENT",
                "Invoice text is empty.",
                step="extract_invoice",
            )

        prompt = f"{self._invoice_prompt()}\n\nInvoice text:\n{text.strip()}"
        logger.info("Extracting invoice from text", extra={"length": len(text.strip())})
        started_at = perf_counter()
        try:
            response = self._get_client().models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise app_error(
                "GEMINI_ERROR",
                "Gemini text extraction failed.",
                step="extract_invoice",
                details={"mode": "text"},
            ) from exc
        finally:
            logger.info(
                "Gemini text extraction finished",
                extra={"duration_ms": round((perf_counter() - started_at) * 1000, 2)},
            )

        payload = self._extract_json_from_text(response.text or "")
        return self._parse_invoice_payload(payload)

    def extract_from_json(self, payload: Any) -> InvoiceData:
        logger.info("Extracting invoice from JSON payload")
        return self._parse_invoice_payload(payload)

    def extract_from_file(self, file_path: str | Path) -> InvoiceData:
        path = Path(file_path).expanduser()
        if not path.exists():
            raise app_error(
                "FILE_NOT_FOUND",
                f"Invoice file not found: {path}",
                step="extract_invoice",
                details={"path": str(path)},
            )
        if path.stat().st_size == 0:
            raise app_error(
                "EMPTY_DOCUMENT",
                f"Invoice file is empty: {path.name}",
                step="extract_invoice",
                details={"path": str(path)},
            )

        logger.info("Extracting invoice from file", extra={"path": str(path)})
        client = self._get_client()
        started_at = perf_counter()
        try:
            uploaded = client.files.upload(file=path)
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[uploaded, self._invoice_prompt()],
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise app_error(
                "OCR_FAILED",
                "Gemini file extraction failed.",
                step="extract_invoice",
                details={"path": str(path)},
            ) from exc
        finally:
            logger.info(
                "Gemini file extraction finished",
                extra={
                    "path": str(path),
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                },
            )

        payload = self._extract_json_from_text(response.text or "")
        return self._parse_invoice_payload(payload)

    def extract_invoice(
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
    ) -> InvoiceData:
        resolved = self._resolver.resolve(
            source,
            pdf_path=pdf_path,
            uploaded_file=uploaded_file,
            text=text,
            invoice_json=invoice_json,
            url=url,
            base64_data=base64_data,
            raw_bytes=raw_bytes,
        )
        return self.extract_from_resolved(resolved)

    def extract_from_resolved(self, resolved: ResolvedInvoiceInput) -> InvoiceData:
        logger.info(
            "Resolved invoice input",
            extra={
                "resolved_kind": resolved.kind,
                "resolved_input_type": resolved.detected_input_type,
                "source_label": resolved.source_label,
            },
        )

        if resolved.kind == "json":
            return self.extract_from_json(resolved.json_data or {})

        if resolved.kind == "text":
            return self.extract_from_text(resolved.text or "")

        if resolved.kind == "binary":
            if resolved.temp_path and resolved.temp_path.exists():
                try:
                    return self.extract_from_file(resolved.temp_path)
                finally:
                    resolved.cleanup()
            raise app_error(
                "INVALID_INPUT",
                "Binary invoice payload could not be materialized.",
                step="extract_invoice",
            )

        if resolved.kind == "file_path":
            path = resolved.path
            if path is None:
                raise app_error(
                    "INVALID_INPUT",
                    "Resolved file input is missing a path.",
                    step="extract_invoice",
                )
            if path.stat().st_size == 0:
                raise app_error(
                    "EMPTY_DOCUMENT",
                    f"Invoice file is empty: {path.name}",
                    step="extract_invoice",
                    details={"path": str(path)},
                )

            if path.suffix.lower() == ".pdf":
                try:
                    extracted_text = PDFParser.extract_text(path)
                    logger.info(
                        "Using PDF text extraction",
                        extra={"path": str(path)},
                    )
                    return self.extract_from_text(extracted_text)
                except Exception:
                    logger.info(
                        "Falling back to Gemini file extraction for PDF",
                        extra={"path": str(path)},
                    )

            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".pdf"}:
                logger.info("Using Gemini file extraction", extra={"path": str(path)})
                return self.extract_from_file(path)

            raise app_error(
                "UNSUPPORTED_FORMAT",
                f"Unsupported file type: {path.suffix}",
                step="extract_invoice",
                details={"path": str(path), "suffix": path.suffix},
            )

        raise app_error(
            "INVALID_INPUT",
            f"Unsupported resolved input kind: {resolved.kind}",
            step="extract_invoice",
        )
