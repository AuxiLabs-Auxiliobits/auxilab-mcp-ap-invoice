from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.date_normalizer import DateNormalizer


class ConfidenceField(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: str | float | int | None = None
    confidence: float = Field(ge=0, le=1)


class LineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: ConfidenceField
    quantity: ConfidenceField
    unit_price: ConfidenceField
    total: ConfidenceField

    @classmethod
    def from_payload(cls, payload: Any) -> "LineItem":
        if isinstance(payload, cls):
            return payload

        if not isinstance(payload, dict):
            raise ValueError("Line item payload must be a mapping.")

        converted = {}
        for field_name in ("description", "quantity", "unit_price", "total"):
            value = payload.get(field_name)
            if isinstance(value, dict) and "value" in value:
                converted[field_name] = value
            else:
                converted[field_name] = {
                    "value": value,
                    "confidence": 1.0 if value not in (None, "") else 0.0,
                }

        return cls.model_validate(converted)


class InvoiceData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    invoice_number: ConfidenceField
    vendor_name: ConfidenceField

    invoice_date: ConfidenceField
    due_date: ConfidenceField

    subtotal: ConfidenceField
    tax: ConfidenceField
    grand_total: ConfidenceField
    discount: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    shipping: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    balance_due: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    purchase_order: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    order_id: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    currency: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    payment_terms: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    bill_to: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    ship_to: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    invoice_type: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )

    line_items: list[LineItem] = Field(default_factory=list)

    @field_validator("line_items", mode="before")
    @classmethod
    def _coerce_line_items(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return [LineItem.from_payload(item) for item in value]
        raise ValueError("line_items must be a list.")

    @classmethod
    def from_payload(cls, payload: Any) -> "InvoiceData":
        if isinstance(payload, cls):
            return payload

        if not isinstance(payload, dict):
            raise ValueError("Invoice payload must be a mapping.")

        converted: dict[str, Any] = {}
        for field_name in (
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
        ):
            value = payload.get(field_name)
            if isinstance(value, dict) and "value" in value and "confidence" in value:
                converted[field_name] = value
            else:
                converted[field_name] = {
                    "value": value,
                    "confidence": 1.0 if value not in (None, "") else 0.0,
                }

        converted["line_items"] = payload.get("line_items", [])

        invoice = cls.model_validate(converted)
        return invoice.normalize_dates()

    def normalize_dates(self) -> "InvoiceData":
        for field_name in ("invoice_date", "due_date"):
            field_value = getattr(self, field_name)
            raw_value = field_value.value
            if raw_value is None:
                continue
            if isinstance(raw_value, str):
                normalized = DateNormalizer.to_iso8601(raw_value)
                if normalized is not None:
                    field_value.value = normalized
        return self
