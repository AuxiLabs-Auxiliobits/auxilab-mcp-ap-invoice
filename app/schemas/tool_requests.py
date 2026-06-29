from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class InvoiceToolRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: Any = None
    pdf_path: str | None = None
    uploaded_file: Any = None
    text: str | None = None
    invoice_json: Any = None
    url: str | None = None
    base64_data: str | None = None
    raw_bytes: bytes | list[int] | None = None

    @model_validator(mode="after")
    def validate_any_input_present(self) -> "InvoiceToolRequest":
        if not any(
            value is not None
            for value in (
                self.source,
                self.pdf_path,
                self.uploaded_file,
                self.text,
                self.invoice_json,
                self.url,
                self.base64_data,
                self.raw_bytes,
            )
        ):
            raise ValueError(
                "At least one invoice input must be provided."
            )
        return self

