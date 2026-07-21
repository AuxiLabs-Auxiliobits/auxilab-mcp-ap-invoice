from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path
from time import perf_counter
from typing import Any

import pypdfium2 as pdfium
from PIL import Image

from app.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    GEMINI_API_KEY,
    MODEL_NAME,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    VISION_PROVIDER,
)
from app.core.errors import app_error
from app.core.logging import get_logger
from app.schemas.invoice import InvoiceData
from app.services.invoice_inputs import InvoiceInputResolver, ResolvedInvoiceInput
from app.services.number_parser import coerce_float
from app.services.pdf_parser import PDFParser


logger = get_logger(__name__)

TEXT_FILE_SUFFIXES = {".txt", ".md", ".csv", ".tsv", ".log"}
IMAGE_FILE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
VISION_PROVIDERS = {"gemini", "anthropic", "openai"}


class LocalInvoiceParser:
    """Parse readable invoice text without any vision model."""

    _invoice_number_patterns = (
        re.compile(r"^\s*#\s*(?P<value>[A-Za-z0-9][A-Za-z0-9\-\/_.]*)\s*$", re.I),
        re.compile(
            r"\binvoice(?:\s*(?:no\.?|number|#))?\s*[:#-]?\s*(?P<value>[A-Za-z0-9][A-Za-z0-9\-\/_.]*)",
            re.I,
        ),
        re.compile(
            r"\binv(?:oice)?\s*(?:no\.?|#)\s*[:#-]?\s*(?P<value>[A-Za-z0-9][A-Za-z0-9\-\/_.]*)",
            re.I,
        ),
    )

    _amount_pattern = re.compile(
        r"(?P<value>\(?[$£€₹]?\s*-?\d[\d,]*(?:\.\d+)?\)?)"
    )
    _line_item_pattern = re.compile(
        r"^(?P<description>.+?)\s+(?P<quantity>\d+(?:\.\d+)?)\s+(?P<unit>[$£€₹]?\s*[\d,]+(?:\.\d+)?)\s+(?P<total>[$£€₹]?\s*[\d,]+(?:\.\d+)?)$"
    )

    _label_groups: dict[str, tuple[str, ...]] = {
        "invoice_date": ("invoice date", "date"),
        "due_date": ("due date", "payment due"),
        "subtotal": ("subtotal", "sub total"),
        "tax": ("tax", "gst", "vat", "sales tax", "service tax"),
        "grand_total": ("grand total", "amount due", "total due", "total"),
        "balance_due": ("balance due", "amount payable"),
        "purchase_order": ("purchase order", "po number", "po no", "po#", "po"),
        "order_id": ("order id", "order no", "order number"),
        "payment_terms": ("payment terms", "terms"),
        "discount_percentage": ("discount %", "discount percentage"),
        "discount_amount": ("discount amount", "discount"),
        "shipping_charges": ("shipping charges", "shipping"),
        "freight_charges": ("freight charges", "freight"),
        "handling_charges": ("handling charges", "handling"),
        "insurance_charges": ("insurance charges", "insurance"),
        "packaging_charges": ("packaging charges", "packaging"),
    }

    _currency_map = {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
        "₹": "INR",
    }

    def parse(self, text: str) -> InvoiceData:
        if not isinstance(text, str) or not text.strip():
            raise app_error(
                "EMPTY_DOCUMENT",
                "Invoice text is empty.",
                step="extract_invoice",
            )

        lines = self._normalize_lines(text)
        payload: dict[str, Any] = {
            "invoice_number": self._field(self._extract_invoice_number(lines), 0.95),
            "vendor_name": self._field(self._extract_vendor_name(lines), 0.7),
            "invoice_date": self._field(self._extract_text_value(lines, self._label_groups["invoice_date"]), 0.92),
            "due_date": self._field(self._extract_text_value(lines, self._label_groups["due_date"]), 0.9),
            "subtotal": self._field(self._extract_amount_value(lines, self._label_groups["subtotal"]), 0.95),
            "tax": self._field(self._extract_amount_value(lines, self._label_groups["tax"]), 0.9),
            "grand_total": self._field(self._extract_amount_value(lines, self._label_groups["grand_total"]), 0.95),
            "balance_due": self._field(self._extract_amount_value(lines, self._label_groups["balance_due"]), 0.9),
            "purchase_order": self._field(self._extract_text_value(lines, self._label_groups["purchase_order"]), 0.85),
            "order_id": self._field(self._extract_text_value(lines, self._label_groups["order_id"]), 0.9),
            "currency": self._field(self._extract_currency(text), 0.75),
            "payment_terms": self._field(self._extract_text_value(lines, self._label_groups["payment_terms"]), 0.75),
            "discount_percentage": self._field(self._extract_discount_percentage(lines), 0.8),
            "discount_amount": self._field(self._extract_discount_amount(lines), 0.8),
            "shipping_charges": self._field(
                self._extract_amount_value(lines, self._label_groups["shipping_charges"]),
                0.85,
            ),
            "freight_charges": self._field(
                self._extract_amount_value(lines, self._label_groups["freight_charges"]),
                0.85,
            ),
            "handling_charges": self._field(
                self._extract_amount_value(lines, self._label_groups["handling_charges"]),
                0.85,
            ),
            "insurance_charges": self._field(
                self._extract_amount_value(lines, self._label_groups["insurance_charges"]),
                0.85,
            ),
            "packaging_charges": self._field(
                self._extract_amount_value(lines, self._label_groups["packaging_charges"]),
                0.85,
            ),
            "bill_to": self._field(None, 0.0),
            "ship_to": self._field(None, 0.0),
            "invoice_type": self._field(self._extract_invoice_type(lines), 0.6),
            "line_items": self._extract_line_items(lines),
            "other_charges": self._extract_other_charges(lines),
        }

        if payload["grand_total"]["value"] is None and payload["balance_due"]["value"] is not None:
            payload["grand_total"] = self._field(payload["balance_due"]["value"], 0.9)

        if payload["invoice_type"]["value"] is None:
            payload["invoice_type"] = self._field(
                "invoice" if any("invoice" in line.casefold() for line in lines[:3]) else None,
                0.6,
            )

        return InvoiceData.from_payload(payload)

    def _normalize_lines(self, text: str) -> list[str]:
        normalized: list[str] = []
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if line:
                normalized.append(line)
        return normalized

    def _field(self, value: Any, confidence: float) -> dict[str, Any]:
        return {
            "value": value,
            "confidence": confidence if value not in (None, "") else 0.0,
        }

    def _extract_invoice_number(self, lines: list[str]) -> str | None:
        for line in lines[:12]:
            for pattern in self._invoice_number_patterns:
                match = pattern.search(line)
                if match:
                    return match.group("value").strip()
        return None

    def _extract_vendor_name(self, lines: list[str]) -> str | None:
        blocked_terms = (
            "invoice",
            "bill to",
            "ship to",
            "subtotal",
            "total",
            "balance due",
            "terms",
            "date",
            "order id",
            "po",
        )
        for line in lines[:8]:
            candidate = re.sub(r"(?i)\binvoice\b.*$", "", line).strip(" :-#|")
            if not candidate or not re.search(r"[A-Za-z]", candidate):
                continue
            lowered = candidate.casefold()
            if any(term in lowered for term in blocked_terms):
                continue
            if len(candidate.split()) > 8:
                continue
            return candidate
        return None

    def _extract_text_value(self, lines: list[str], aliases: tuple[str, ...]) -> str | None:
        for index, line in enumerate(lines):
            for alias in aliases:
                value = self._text_after_alias(line, alias)
                if value:
                    return value
                if self._line_matches_alias(line, alias) and index + 1 < len(lines):
                    next_line = lines[index + 1]
                    if not self._looks_like_label(next_line):
                        return next_line
        return None

    def _extract_amount_value(self, lines: list[str], aliases: tuple[str, ...]) -> float | None:
        for line in lines:
            for alias in aliases:
                if not self._line_matches_alias(line, alias):
                    continue
                amount = self._parse_amount(self._text_after_alias(line, alias) or line)
                if amount is not None:
                    return amount
        return None

    def _extract_currency(self, text: str) -> str | None:
        for symbol, currency_code in self._currency_map.items():
            if symbol in text:
                return currency_code
        match = re.search(r"\b(USD|EUR|GBP|INR|CAD|AUD|NZD|CHF|JPY)\b", text, re.I)
        if match:
            return match.group(1).upper()
        return None

    def _extract_invoice_type(self, lines: list[str]) -> str | None:
        joined = " ".join(lines[:3]).casefold()
        if "credit note" in joined:
            return "credit note"
        if "debit note" in joined:
            return "debit note"
        if "invoice" in joined:
            return "invoice"
        return None

    def _extract_discount_percentage(self, lines: list[str]) -> float | None:
        for line in lines:
            lowered = line.casefold()
            if "discount" not in lowered or "%" not in line:
                continue
            match = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
            if match:
                return float(match.group(1))
        return None

    def _extract_discount_amount(self, lines: list[str]) -> float | None:
        for line in lines:
            lowered = line.casefold()
            if "discount" not in lowered or "%" in line:
                continue
            amount = self._parse_amount(line)
            if amount is not None:
                return amount
        return None

    def _extract_line_items(self, lines: list[str]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for line in lines:
            if self._looks_like_label(line):
                continue
            match = self._line_item_pattern.match(line)
            if not match:
                continue

            description = match.group("description").strip()
            if not description or len(description) < 2:
                continue

            quantity = self._parse_amount(match.group("quantity"))
            unit_price = self._parse_amount(match.group("unit"))
            total = self._parse_amount(match.group("total"))
            if quantity is None or unit_price is None or total is None:
                continue

            items.append(
                {
                    "description": self._field(description, 0.8),
                    "quantity": self._field(quantity, 0.8),
                    "unit_price": self._field(unit_price, 0.8),
                    "total": self._field(total, 0.8),
                }
            )
        return items

    def _extract_other_charges(self, lines: list[str]) -> list[dict[str, Any]]:
        other_charges: list[dict[str, Any]] = []
        known_labels = {
            *self._label_groups["subtotal"],
            *self._label_groups["grand_total"],
            *self._label_groups["balance_due"],
            *self._label_groups["invoice_date"],
            *self._label_groups["due_date"],
            *self._label_groups["purchase_order"],
            *self._label_groups["order_id"],
            "invoice number",
            "invoice #",
        }

        for line in lines:
            lowered = line.casefold()
            if any(label in lowered for label in known_labels):
                continue
            if not any(token in lowered for token in ("charge", "charges", "fee", "fees", "surcharge", "adjustment")):
                continue
            amount = self._parse_amount(line)
            if amount is None:
                continue
            name = line
            amount_text = self._amount_pattern.search(line)
            if amount_text is not None:
                name = line[: amount_text.start()].strip(" :-#")
            if not name:
                name = "other_charge"
            other_charges.append(
                {
                    "name": self._field(name, 0.7),
                    "amount": self._field(amount, 0.8),
                }
            )
        return other_charges

    def _parse_amount(self, value: str | float | int | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        match = self._amount_pattern.search(value)
        if not match:
            return None
        candidate = match.group("value").replace(" ", "")
        try:
            return coerce_float(candidate)
        except ValueError:
            return None

    def _text_after_alias(self, line: str, alias: str) -> str | None:
        if alias == "#":
            match = re.match(r"^\s*#\s*(?P<value>.+?)\s*$", line)
            if match:
                value = match.group("value").strip(" :-#")
                return value or None
            return None

        pattern = re.compile(
            rf"\b{re.escape(alias)}\b\s*[:#-]?\s*(?P<value>.+?)\s*$",
            re.I,
        )
        match = pattern.search(line)
        if not match:
            return None
        value = match.group("value").strip(" :-#|")
        if not value:
            return None
        if self._looks_like_label(value):
            return None
        return value

    def _line_matches_alias(self, line: str, alias: str) -> bool:
        if alias == "#":
            return bool(re.match(r"^\s*#\s*", line))
        return bool(re.search(rf"\b{re.escape(alias)}\b", line, re.I))

    def _looks_like_label(self, line: str) -> bool:
        lowered = line.casefold()
        label_tokens = (
            "invoice",
            "bill to",
            "ship to",
            "subtotal",
            "total",
            "balance due",
            "terms",
            "date",
            "order id",
            "quantity",
            "rate",
            "amount",
        )
        return any(token in lowered for token in label_tokens)


class GeminiService:
    def __init__(self) -> None:
        self._resolver = InvoiceInputResolver()
        self._local_parser = LocalInvoiceParser()
        self._gemini_client: Any = None
        self._anthropic_client: Any = None
        self._openai_client: Any = None

    def _resolved_provider(self) -> str | None:
        provider = (VISION_PROVIDER or "").strip().lower() or None
        if provider is not None:
            if provider not in VISION_PROVIDERS:
                raise app_error(
                    "INVALID_CONFIG",
                    f"Unsupported vision provider: {provider}",
                    step="extract_invoice",
                    details={"allowed": sorted(VISION_PROVIDERS)},
                )
            return provider

        return None

    def _vision_model(self, provider: str) -> str:
        if provider == "gemini":
            return MODEL_NAME
        if provider == "anthropic":
            return ANTHROPIC_MODEL
        if provider == "openai":
            return OPENAI_MODEL
        raise app_error(
            "INVALID_CONFIG",
            f"Unsupported vision provider: {provider}",
            step="extract_invoice",
            details={"allowed": sorted(VISION_PROVIDERS)},
        )

    def _invoice_prompt(self) -> str:
        return """
You are an Accounts Payable Invoice Extraction AI.

Extract every invoice field accurately, especially all monetary adjustments shown on the invoice.

Rules:

- Never invent values.
- Only extract values explicitly written on the invoice.
- Never calculate or infer values yourself.
- If a field is missing, return {"value": null, "confidence": 0}.
- Confidence between 0 and 1.
- Return only valid JSON.
- Use the tax field for GST, VAT, sales tax, or similar invoice tax amounts.
- Never assume tax is zero just because other charges or discounts exist.
- If a discount percentage is shown, extract both the percentage and the amount.
- If there are multiple additional charges, include every one in other_charges.
- If no additional charges are visible, return other_charges as an empty array.

Return this schema:
{
  "invoice_number": {"value": null, "confidence": 0},
  "vendor_name": {"value": null, "confidence": 0},
  "invoice_date": {"value": null, "confidence": 0},
  "due_date": {"value": null, "confidence": 0},
  "subtotal": {"value": null, "confidence": 0},
  "discount_percentage": {"value": null, "confidence": 0},
  "discount_amount": {"value": null, "confidence": 0},
  "tax": {"value": null, "confidence": 0},
  "shipping_charges": {"value": null, "confidence": 0},
  "freight_charges": {"value": null, "confidence": 0},
  "handling_charges": {"value": null, "confidence": 0},
  "insurance_charges": {"value": null, "confidence": 0},
  "packaging_charges": {"value": null, "confidence": 0},
  "other_charges": [],
  "grand_total": {"value": null, "confidence": 0},
  "balance_due": {"value": null, "confidence": 0},
  "purchase_order": {"value": null, "confidence": 0},
  "order_id": {"value": null, "confidence": 0},
  "currency": {"value": null, "confidence": 0},
  "payment_terms": {"value": null, "confidence": 0},
  "bill_to": {"value": null, "confidence": 0},
  "ship_to": {"value": null, "confidence": 0},
  "invoice_type": {"value": null, "confidence": 0},
  "line_items": [
    {
      "description": {"value": null, "confidence": 0},
      "quantity": {"value": null, "confidence": 0},
      "unit_price": {"value": null, "confidence": 0},
      "total": {"value": null, "confidence": 0}
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
            "Vision provider response did not contain valid JSON.",
            step="extract_invoice",
        )

    def extract_from_text(self, text: str) -> InvoiceData:
        logger.info("Extracting invoice from readable text locally", extra={"length": len(text.strip()) if isinstance(text, str) else 0})
        started_at = perf_counter()
        try:
            return self._local_parser.parse(text)
        finally:
            logger.info(
                "Local text extraction finished",
                extra={"duration_ms": round((perf_counter() - started_at) * 1000, 2)},
            )

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

        provider = self._resolved_provider()
        if provider is None:
            raise app_error(
                "VISION_PROVIDER_REQUIRED",
                "No vision provider is configured for image or scanned PDF extraction.",
                step="extract_invoice",
                details={"allowed": sorted(VISION_PROVIDERS)},
            )

        logger.info(
            "Extracting invoice with vision provider",
            extra={"path": str(path), "provider": provider},
        )
        started_at = perf_counter()
        try:
            if provider == "gemini":
                payload = self._extract_with_gemini(path)
            else:
                payload = self._extract_with_open_vision_provider(provider, path)
            return self._parse_invoice_payload(payload)
        finally:
            logger.info(
                "Vision extraction finished",
                extra={
                    "path": str(path),
                    "provider": provider,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                },
            )

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
        try:
            return self.extract_from_resolved(resolved)
        finally:
            resolved.cleanup()

    def extract_from_resolved(self, resolved: ResolvedInvoiceInput) -> InvoiceData:
        logger.info(
            "Resolved invoice input",
            extra={
                "resolved_kind": resolved.kind,
                "resolved_input_type": resolved.detected_input_type,
                "source_label": resolved.source_label,
            },
        )

        try:
            if resolved.kind == "json":
                return self.extract_from_json(resolved.json_data or {})

            if resolved.kind == "text":
                return self.extract_from_text(resolved.text or "")

            if resolved.kind == "binary":
                if resolved.temp_path and resolved.temp_path.exists():
                    return self.extract_from_file_or_text(resolved.temp_path)
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
                return self.extract_from_file_or_text(path)

            raise app_error(
                "INVALID_INPUT",
                f"Unsupported resolved input kind: {resolved.kind}",
                step="extract_invoice",
            )
        finally:
            if resolved.kind == "binary":
                resolved.cleanup()

    def extract_from_file_or_text(self, path: Path) -> InvoiceData:
        suffix = path.suffix.lower()
        if suffix in TEXT_FILE_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                raise app_error(
                    "EMPTY_DOCUMENT",
                    f"Invoice text file is empty: {path.name}",
                    step="extract_invoice",
                    details={"path": str(path)},
                )
            logger.info("Using local text extraction for text file", extra={"path": str(path)})
            return self.extract_from_text(text)

        if suffix == ".pdf":
            try:
                extracted_text = PDFParser.extract_text(path)
            except Exception:
                provider = self._resolved_provider()
                if provider is None:
                    raise
                logger.info(
                    "Falling back to vision provider for PDF without readable text",
                    extra={"path": str(path), "provider": provider},
                )
                return self.extract_from_file(path)

            logger.info("Using pdfplumber text extraction", extra={"path": str(path)})
            return self.extract_from_text(extracted_text)

        if suffix in IMAGE_FILE_SUFFIXES:
            return self.extract_from_file(path)

        raise app_error(
            "UNSUPPORTED_FORMAT",
            f"Unsupported file type: {path.suffix}",
            step="extract_invoice",
            details={"path": str(path), "suffix": path.suffix},
        )

    def _extract_with_gemini(self, path: Path) -> dict[str, Any]:
        if not GEMINI_API_KEY:
            raise app_error(
                "CONFIG_ERROR",
                "GEMINI_API_KEY is required when VISION_PROVIDER is set to gemini.",
                step="extract_invoice",
            )

        try:
            from google import genai
            from google.genai import types
        except ModuleNotFoundError as exc:
            raise app_error(
                "CONFIG_ERROR",
                "google-genai is not installed.",
                step="extract_invoice",
            ) from exc

        if self._gemini_client is None:
            self._gemini_client = genai.Client(api_key=GEMINI_API_KEY)

        client = self._gemini_client
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
                "Gemini extraction finished",
                extra={"path": str(path), "duration_ms": round((perf_counter() - started_at) * 1000, 2)},
            )

        return self._extract_json_from_text(response.text or "")

    def _extract_with_open_vision_provider(self, provider: str, path: Path) -> dict[str, Any]:
        prompt = self._invoice_prompt()
        image_payloads = self._build_image_payloads(path)
        if not image_payloads:
            raise app_error(
                "EMPTY_DOCUMENT",
                f"No readable pages or images found in {path.name}.",
                step="extract_invoice",
                details={"path": str(path)},
            )

        if provider == "anthropic":
            if not ANTHROPIC_API_KEY:
                raise app_error(
                    "CONFIG_ERROR",
                    "ANTHROPIC_API_KEY is required when VISION_PROVIDER=anthropic.",
                    step="extract_invoice",
                )
            try:
                from anthropic import Anthropic
            except ModuleNotFoundError as exc:
                raise app_error(
                    "CONFIG_ERROR",
                    "anthropic is not installed.",
                    step="extract_invoice",
                ) from exc

            if self._anthropic_client is None:
                self._anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

            started_at = perf_counter()
            try:
                content = [{"type": "text", "text": prompt}]
                for payload in image_payloads:
                    content.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": payload["mime_type"],
                                "data": payload["base64"],
                            },
                        }
                    )

                response = self._anthropic_client.messages.create(
                    model=ANTHROPIC_MODEL,
                    max_tokens=4096,
                    temperature=0,
                    messages=[{"role": "user", "content": content}],
                )
            except Exception as exc:  # noqa: BLE001
                raise app_error(
                    "OCR_FAILED",
                    "Anthropic file extraction failed.",
                    step="extract_invoice",
                    details={"path": str(path)},
                ) from exc
            finally:
                logger.info(
                    "Anthropic extraction finished",
                    extra={"path": str(path), "duration_ms": round((perf_counter() - started_at) * 1000, 2)},
                )

            response_text = "".join(
                block.text for block in getattr(response, "content", []) if getattr(block, "type", None) == "text"
            )
            return self._extract_json_from_text(response_text)

        if provider == "openai":
            if not OPENAI_API_KEY:
                raise app_error(
                    "CONFIG_ERROR",
                    "OPENAI_API_KEY is required when VISION_PROVIDER=openai.",
                    step="extract_invoice",
                )
            try:
                from openai import OpenAI
            except ModuleNotFoundError as exc:
                raise app_error(
                    "CONFIG_ERROR",
                    "openai is not installed.",
                    step="extract_invoice",
                ) from exc

            if self._openai_client is None:
                self._openai_client = OpenAI(api_key=OPENAI_API_KEY)

            started_at = perf_counter()
            try:
                content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
                for payload in image_payloads:
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": payload["data_url"]},
                        }
                    )

                response = self._openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": content}],
                )
            except Exception as exc:  # noqa: BLE001
                raise app_error(
                    "OCR_FAILED",
                    "OpenAI file extraction failed.",
                    step="extract_invoice",
                    details={"path": str(path)},
                ) from exc
            finally:
                logger.info(
                    "OpenAI extraction finished",
                    extra={"path": str(path), "duration_ms": round((perf_counter() - started_at) * 1000, 2)},
                )

            response_text = response.choices[0].message.content or ""
            return self._extract_json_from_text(response_text)

        raise app_error(
            "INVALID_CONFIG",
            f"Unsupported vision provider: {provider}",
            step="extract_invoice",
            details={"allowed": sorted(VISION_PROVIDERS)},
        )

    def _build_image_payloads(self, path: Path) -> list[dict[str, str]]:
        suffix = path.suffix.lower()
        payloads: list[dict[str, str]] = []

        if suffix in IMAGE_FILE_SUFFIXES:
            image = Image.open(path).convert("RGB")
            payloads.append(self._image_to_payload(image))
            return payloads

        if suffix != ".pdf":
            return payloads

        document = pdfium.PdfDocument(str(path))
        try:
            for index in range(len(document)):
                page = document[index]
                bitmap = page.render(scale=2)
                image = bitmap.to_pil().convert("RGB")
                payloads.append(self._image_to_payload(image, page_number=index + 1))
        finally:
            document.close()

        return payloads

    def _image_to_payload(self, image: Image.Image, *, page_number: int | None = None) -> dict[str, str]:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        payload = {
            "mime_type": "image/png",
            "base64": encoded,
            "data_url": f"data:image/png;base64,{encoded}",
        }
        if page_number is not None:
            payload["page_number"] = str(page_number)
        return payload
