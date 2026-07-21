from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.date_normalizer import DateNormalizer


class ConfidenceField(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: str | float | int | None = None
    confidence: float = Field(ge=0, le=1)


def _confidence_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and "value" in value:
        confidence = value.get("confidence", 0.0)
        return {
            "value": value.get("value"),
            "confidence": confidence if confidence is not None else 0.0,
        }

    return {
        "value": value,
        "confidence": 1.0 if value not in (None, "") else 0.0,
    }


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

        converted: dict[str, Any] = {}
        for field_name in ("description", "quantity", "unit_price", "total"):
            converted[field_name] = _confidence_payload(payload.get(field_name))

        return cls.model_validate(converted)


class ChargeItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: ConfidenceField
    amount: ConfidenceField

    @classmethod
    def from_payload(cls, payload: Any) -> "ChargeItem":
        if isinstance(payload, cls):
            return payload

        if not isinstance(payload, dict):
            raise ValueError("Charge item payload must be a mapping.")

        converted = {
            "name": _confidence_payload(payload.get("name")),
            "amount": _confidence_payload(payload.get("amount")),
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
    discount_percentage: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    discount_amount: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    shipping_charges: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    freight_charges: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    handling_charges: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    insurance_charges: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    packaging_charges: ConfidenceField = Field(
        default_factory=lambda: ConfidenceField(value=None, confidence=0.0)
    )
    other_charges: list[ChargeItem] = Field(default_factory=list)
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

    @field_validator("other_charges", mode="before")
    @classmethod
    def _coerce_other_charges(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return [ChargeItem.from_payload(item) for item in value]
        raise ValueError("other_charges must be a list.")

    @classmethod
    def from_payload(cls, payload: Any) -> "InvoiceData":
        if isinstance(payload, cls):
            return payload

        if not isinstance(payload, dict):
            raise ValueError("Invoice payload must be a mapping.")

        alias_map = {
            "discount_percentage": ("discount_percentage",),
            "discount_amount": ("discount_amount", "discount"),
            "shipping_charges": ("shipping_charges", "shipping"),
            "freight_charges": ("freight_charges",),
            "handling_charges": ("handling_charges",),
            "insurance_charges": ("insurance_charges",),
            "packaging_charges": ("packaging_charges",),
            "other_charges": ("other_charges",),
        }

        converted: dict[str, Any] = {}
        for field_name in (
            "invoice_number",
            "vendor_name",
            "invoice_date",
            "due_date",
            "subtotal",
            "tax",
            "grand_total",
            "discount_percentage",
            "discount_amount",
            "shipping_charges",
            "freight_charges",
            "handling_charges",
            "insurance_charges",
            "packaging_charges",
            "balance_due",
            "purchase_order",
            "order_id",
            "currency",
            "payment_terms",
            "bill_to",
            "ship_to",
            "invoice_type",
        ):
            value = None
            for candidate_key in alias_map.get(field_name, (field_name,)):
                if candidate_key in payload:
                    value = payload.get(candidate_key)
                    break
            converted[field_name] = _confidence_payload(value)

        converted["line_items"] = payload.get("line_items", [])
        converted["other_charges"] = payload.get("other_charges", [])

        invoice = cls.model_validate(converted)
        return invoice.normalize_dates()

    @property
    def discount(self) -> ConfidenceField:
        return self.discount_amount

    @property
    def shipping(self) -> ConfidenceField:
        return self.shipping_charges

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
