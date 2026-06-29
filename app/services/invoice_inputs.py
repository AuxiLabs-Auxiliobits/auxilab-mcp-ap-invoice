from __future__ import annotations

import base64
import binascii
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

from app.config import INVOICE_URL_TIMEOUT_SECONDS
from app.core.errors import app_error
from app.schemas.tool_requests import InvoiceToolRequest


INVOICE_FIELD_HINTS = {
    "invoice_number",
    "vendor_name",
    "invoice_date",
    "due_date",
    "subtotal",
    "tax",
    "grand_total",
    "discount",
    "shipping",
    "balance_due",
    "purchase_order",
    "order_id",
    "currency",
    "payment_terms",
    "bill_to",
    "ship_to",
    "invoice_type",
    "line_items",
}

UPLOAD_CONTAINER_KEYS = (
    "file",
    "files",
    "upload",
    "uploaded_file",
    "uploaded_files",
    "attachment",
    "attachments",
    "document",
    "documents",
    "source",
)


@dataclass(slots=True)
class ResolvedInvoiceInput:
    kind: str
    source_label: str
    detected_input_type: str
    path: Path | None = None
    text: str | None = None
    json_data: dict[str, Any] | None = None
    binary: bytes | None = None
    filename: str | None = None
    mime_type: str | None = None
    temp_path: Path | None = None
    original: Any = None
    url: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def cleanup(self) -> None:
        for candidate in (self.temp_path,):
            if candidate is not None:
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    pass


class InvoiceInputResolver:
    def resolve(
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
    ) -> ResolvedInvoiceInput:
        request = InvoiceToolRequest(
            source=source,
            pdf_path=pdf_path,
            uploaded_file=uploaded_file,
            text=text,
            invoice_json=invoice_json,
            url=url,
            base64_data=base64_data,
            raw_bytes=raw_bytes,
        )

        if request.invoice_json is not None:
            return self._from_json_payload(
                request.invoice_json,
                source_label="invoice_json",
                detected_input_type="invoice_json",
            )

        if request.text is not None:
            return self._from_text_like(
                request.text,
                source_label="text",
                detected_input_type="invoice_text",
            )

        if request.pdf_path is not None:
            return self._from_path(
                request.pdf_path,
                source_label="pdf_path",
                detected_input_type="file_path",
            )

        if request.url is not None:
            return self._from_url(request.url, source_label="url")

        if request.base64_data is not None:
            return self._from_base64(
                request.base64_data,
                filename=None,
                mime_type=None,
                source_label="base64_data",
                detected_input_type="base64_data",
                original=request.base64_data,
            )

        if request.raw_bytes is not None:
            return self._from_bytes_like(
                request.raw_bytes,
                source_label="raw_bytes",
                detected_input_type="raw_bytes",
                original=request.raw_bytes,
            )

        return self._from_any(request.source if request.source is not None else request.uploaded_file)

    def _from_any(self, source: Any) -> ResolvedInvoiceInput:
        if source is None:
            raise app_error(
                "INVALID_INPUT",
                "No invoice input provided.",
                step="resolve_input",
            )

        if isinstance(source, bytes):
            return self._from_bytes_like(
                source,
                source_label="bytes",
                detected_input_type="raw_bytes",
                original=source,
            )

        if isinstance(source, bytearray):
            return self._from_bytes_like(
                bytes(source),
                source_label="bytearray",
                detected_input_type="raw_bytes",
                original=source,
            )

        if isinstance(source, list) and all(isinstance(item, int) for item in source):
            return self._from_bytes_like(
                source,
                source_label="byte_list",
                detected_input_type="byte_array",
                original=source,
            )

        if isinstance(source, Path):
            return self._from_path(
                str(source),
                source_label="path",
                detected_input_type="file_path",
            )

        if isinstance(source, Mapping):
            return self._from_maybe_mapping(source, source_label="mapping")

        if isinstance(source, str):
            return self._from_string(source)

        raise app_error(
            "INVALID_INPUT",
            f"Unsupported invoice input type: {type(source).__name__}",
            step="resolve_input",
            details={"input_type": type(source).__name__},
        )

    def _from_string(self, value: str) -> ResolvedInvoiceInput:
        stripped = value.strip()
        if not stripped:
            raise app_error(
                "INVALID_INPUT",
                "Invoice input string is empty.",
                step="resolve_input",
            )

        if stripped.startswith("data:"):
            return self._from_data_uri(stripped, source_label="data_uri")

        if stripped.startswith("file://"):
            parsed = urlparse(stripped)
            path = unquote(parsed.path)
            if parsed.netloc and not path.startswith("/"):
                path = f"//{parsed.netloc}/{path}"
            if path.startswith("/") and len(path) > 2 and path[2] == ":":
                path = path.lstrip("/")
            return self._from_path(
                path,
                source_label="file_uri",
                detected_input_type="file_uri",
            )

        if stripped.lower().startswith(("http://", "https://")):
            return self._from_url(stripped, source_label="source")

        try:
            parsed_json = json.loads(stripped)
        except json.JSONDecodeError:
            parsed_json = None

        if isinstance(parsed_json, Mapping):
            return self._from_json_payload(
                parsed_json,
                source_label="json_string",
                detected_input_type="invoice_json",
            )

        if self._looks_like_base64(stripped):
            return self._from_base64(
                stripped,
                filename=None,
                mime_type=None,
                source_label="source",
                detected_input_type="base64_data",
                original=value,
            )

        return self._from_path_or_text(stripped, source_label="path_or_text")

    def _from_text_like(
        self,
        value: str,
        *,
        source_label: str,
        detected_input_type: str,
    ) -> ResolvedInvoiceInput:
        stripped = value.strip()
        if not stripped:
            raise app_error(
                "EMPTY_DOCUMENT",
                "Invoice text is empty.",
                step="resolve_input",
            )

        try:
            parsed_json = json.loads(stripped)
        except json.JSONDecodeError:
            parsed_json = None

        if isinstance(parsed_json, Mapping):
            return self._from_json_payload(
                parsed_json,
                source_label=source_label,
                detected_input_type="invoice_json",
            )

        return ResolvedInvoiceInput(
            kind="text",
            source_label=source_label,
            detected_input_type=detected_input_type,
            text=stripped,
            original=value,
            details={"length": len(stripped)},
        )

    def _from_maybe_mapping(
        self,
        payload: Mapping[str, Any],
        *,
        source_label: str,
    ) -> ResolvedInvoiceInput:
        normalized_keys = {str(key).lower(): key for key in payload.keys()}

        if self._looks_like_invoice_json(payload):
            return self._from_json_payload(
                payload,
                source_label=source_label,
                detected_input_type="invoice_json",
            )

        for nested_key in UPLOAD_CONTAINER_KEYS:
            original_key = normalized_keys.get(nested_key)
            if original_key is None:
                continue
            nested_value = payload.get(original_key)
            if isinstance(nested_value, list) and nested_value:
                return self._from_any(nested_value[0])
            if nested_value is not None and nested_value is not payload:
                try:
                    return self._from_any(nested_value)
                except Exception:
                    pass

        path_value = self._first_mapping_value(
            payload,
            "path",
            "file_path",
            "pdf_path",
            "uri",
            "local_path",
            "temp_path",
            "pathname",
        )
        if isinstance(path_value, str) and path_value.strip():
            return self._from_string(path_value)

        url_value = self._first_mapping_value(payload, "url", "download_url", "href")
        if isinstance(url_value, str) and url_value.strip():
            return self._from_url(url_value, source_label=source_label)

        text_value = self._first_mapping_value(
            payload,
            "text",
            "content",
            "body",
            "invoice_text",
            "raw_text",
        )
        if isinstance(text_value, str) and text_value.strip():
            return self._from_text_like(
                text_value,
                source_label=source_label,
                detected_input_type="invoice_text",
            )

        base64_value = self._first_mapping_value(
            payload,
            "base64",
            "data_base64",
            "base64_data",
            "blob",
            "data",
        )
        mime_type = self._first_mapping_value(
            payload,
            "mime_type",
            "mimetype",
            "content_type",
            "media_type",
            "mimeType",
        )
        filename = self._first_mapping_value(
            payload,
            "filename",
            "name",
            "file_name",
            "original_name",
            "title",
        )
        if isinstance(base64_value, str) and base64_value.strip():
            if base64_value.strip().startswith("data:"):
                return self._from_data_uri(
                    base64_value,
                    source_label=source_label,
                    filename=filename if isinstance(filename, str) else None,
                )
            if self._looks_like_base64(base64_value):
                return self._from_base64(
                    base64_value,
                    filename=filename if isinstance(filename, str) else None,
                    mime_type=mime_type if isinstance(mime_type, str) else None,
                    source_label=source_label,
                    detected_input_type="base64_data",
                    original=dict(payload),
                )

        bytes_value = self._first_mapping_value(
            payload,
            "bytes",
            "raw_bytes",
            "byte_array",
            "data_bytes",
            "content_bytes",
        )
        if bytes_value is not None:
            return self._from_bytes_like(
                bytes_value,
                source_label=source_label,
                detected_input_type="raw_bytes",
                filename=filename if isinstance(filename, str) else None,
                mime_type=mime_type if isinstance(mime_type, str) else None,
                original=dict(payload),
            )

        raise app_error(
            "INVALID_INPUT",
            "Could not infer invoice input from mapping payload.",
            step="resolve_input",
            details={"keys": sorted(str(key) for key in payload.keys())},
        )

    def _from_json_payload(
        self,
        payload: Any,
        *,
        source_label: str,
        detected_input_type: str,
    ) -> ResolvedInvoiceInput:
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise app_error(
                    "VALIDATION_ERROR",
                    "Invoice JSON payload is not valid JSON.",
                    step="resolve_input",
                ) from exc

        if not isinstance(payload, Mapping):
            raise app_error(
                "VALIDATION_ERROR",
                "Invoice JSON payload must be a mapping.",
                step="resolve_input",
            )

        return ResolvedInvoiceInput(
            kind="json",
            source_label=source_label,
            detected_input_type=detected_input_type,
            json_data=dict(payload),
            original=dict(payload),
        )

    def _from_path(
        self,
        raw_path: str,
        *,
        source_label: str,
        detected_input_type: str,
    ) -> ResolvedInvoiceInput:
        candidate = self._resolve_existing_path(raw_path)
        if candidate is None or not candidate.is_file():
            raise app_error(
                "FILE_NOT_FOUND",
                f"Invoice file not found: {raw_path}",
                step="resolve_input",
                details={"path": raw_path},
            )

        return ResolvedInvoiceInput(
            kind="file_path",
            source_label=source_label,
            detected_input_type=detected_input_type,
            path=candidate,
            filename=candidate.name,
            original=raw_path,
            details={"path": str(candidate)},
        )

    def _from_path_or_text(self, value: str, *, source_label: str) -> ResolvedInvoiceInput:
        candidate = self._resolve_existing_path(value)
        if candidate is not None and candidate.is_file():
            return self._from_path(
                str(candidate),
                source_label=source_label,
                detected_input_type="file_path",
            )

        return self._from_text_like(
            value,
            source_label=source_label,
            detected_input_type="invoice_text",
        )

    def _from_url(self, value: str, *, source_label: str) -> ResolvedInvoiceInput:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"}:
            raise app_error(
                "INVALID_INPUT",
                f"Unsupported URL scheme: {parsed.scheme}",
                step="resolve_input",
                details={"url": value},
            )

        try:
            with urlopen(value, timeout=INVOICE_URL_TIMEOUT_SECONDS) as response:
                content = response.read()
                mime_type = response.headers.get_content_type()
                filename = Path(parsed.path).name or None
        except OSError as exc:
            raise app_error(
                "FILE_NOT_FOUND",
                f"Could not fetch invoice URL: {value}",
                step="resolve_input",
                details={"url": value},
            ) from exc

        return self._from_bytes_like(
            content,
            source_label=source_label,
            detected_input_type="url",
            filename=filename,
            mime_type=mime_type,
            original=value,
            url=value,
        )

    def _from_data_uri(
        self,
        value: str,
        *,
        source_label: str,
        filename: str | None = None,
    ) -> ResolvedInvoiceInput:
        header, _, data = value.partition(",")
        if not data:
            raise app_error(
                "INVALID_INPUT",
                "Data URI did not contain payload data.",
                step="resolve_input",
            )

        mime_type = header[5:].split(";")[0] if header.startswith("data:") else None
        return self._from_base64(
            data,
            filename=filename,
            mime_type=mime_type,
            source_label=source_label,
            detected_input_type="base64_data",
            original=value,
        )

    def _from_base64(
        self,
        encoded: str,
        *,
        filename: str | None,
        mime_type: str | None,
        source_label: str,
        detected_input_type: str,
        original: Any,
    ) -> ResolvedInvoiceInput:
        try:
            binary = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise app_error(
                "INVALID_INPUT",
                "Invalid base64 invoice payload.",
                step="resolve_input",
            ) from exc

        return self._from_bytes_like(
            binary,
            source_label=source_label,
            detected_input_type=detected_input_type,
            filename=filename,
            mime_type=mime_type,
            original=original,
        )

    def _from_bytes_like(
        self,
        value: bytes | list[int],
        *,
        source_label: str,
        detected_input_type: str,
        filename: str | None = None,
        mime_type: str | None = None,
        original: Any,
        url: str | None = None,
    ) -> ResolvedInvoiceInput:
        if isinstance(value, list):
            try:
                binary = bytes(value)
            except ValueError as exc:
                raise app_error(
                    "INVALID_INPUT",
                    "Byte array payload contains invalid values.",
                    step="resolve_input",
                ) from exc
        else:
            binary = bytes(value)

        if not binary:
            raise app_error(
                "EMPTY_DOCUMENT",
                "Binary invoice payload is empty.",
                step="resolve_input",
            )

        guessed_mime = mime_type or self._guess_mime_type(binary)
        suffix = Path(filename or "uploaded_invoice").suffix or self._suffix_from_mime(guessed_mime)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = Path(temp_file.name)
        try:
            temp_file.write(binary)
            temp_file.flush()
        finally:
            temp_file.close()

        return ResolvedInvoiceInput(
            kind="binary",
            source_label=source_label,
            detected_input_type=detected_input_type,
            binary=binary,
            filename=filename or temp_path.name,
            mime_type=guessed_mime,
            temp_path=temp_path,
            original=original,
            url=url,
            details={"size_bytes": len(binary), "mime_type": guessed_mime},
        )

    def _looks_like_invoice_json(self, payload: Mapping[str, Any]) -> bool:
        keys = {str(key).lower() for key in payload.keys()}
        return bool(keys & INVOICE_FIELD_HINTS)

    def _looks_like_base64(self, value: str) -> bool:
        candidate = "".join(value.strip().split())
        if len(candidate) < 32 or len(candidate) % 4 != 0:
            return False
        try:
            base64.b64decode(candidate, validate=True)
            return True
        except (ValueError, binascii.Error):
            return False

    def _guess_mime_type(self, content: bytes) -> str | None:
        if content.startswith(b"%PDF"):
            return "application/pdf"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            return "image/webp"
        return None

    def _resolve_existing_path(self, raw_path: str) -> Path | None:
        candidate = Path(raw_path).expanduser()
        if candidate.exists():
            return candidate.resolve()

        if not candidate.is_absolute():
            project_root = Path(__file__).resolve().parents[2]
            relative_candidates = [
                (Path.cwd() / candidate).resolve(),
                (project_root / candidate).resolve(),
            ]
            for path in relative_candidates:
                if path.exists():
                    return path
        return None

    def _suffix_from_mime(self, mime_type: str | None) -> str:
        if not mime_type:
            return ".bin"

        value = mime_type.lower()
        if "pdf" in value:
            return ".pdf"
        if "png" in value:
            return ".png"
        if "jpeg" in value or "jpg" in value:
            return ".jpg"
        if "webp" in value:
            return ".webp"
        if value.startswith("text/"):
            return ".txt"
        return ".bin"

    def _first_mapping_value(self, payload: Mapping[str, Any], *names: str) -> Any:
        lowered = {str(key).lower(): key for key in payload.keys()}
        for name in names:
            original_key = lowered.get(name.lower())
            if original_key is not None:
                return payload.get(original_key)
        return None

