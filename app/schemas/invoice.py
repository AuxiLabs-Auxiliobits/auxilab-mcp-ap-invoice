from typing import List, Optional

from pydantic import BaseModel, Field


class ConfidenceField(BaseModel):
    value: Optional[str | float] = None
    confidence: float = Field(ge=0, le=1)


class LineItem(BaseModel):
    description: ConfidenceField
    quantity: ConfidenceField
    unit_price: ConfidenceField
    total: ConfidenceField


class OtherCharge(BaseModel):
    name: ConfidenceField
    amount: ConfidenceField


def missing_confidence_field() -> ConfidenceField:
    return ConfidenceField(value=None, confidence=0.0)


class InvoiceData(BaseModel):
    invoice_number: ConfidenceField
    vendor_name: ConfidenceField

    invoice_date: ConfidenceField
    due_date: ConfidenceField

    subtotal: ConfidenceField = Field(default_factory=missing_confidence_field)
    discount_percentage: ConfidenceField = Field(default_factory=missing_confidence_field)
    discount_amount: ConfidenceField = Field(default_factory=missing_confidence_field)
    tax: ConfidenceField = Field(default_factory=missing_confidence_field)
    shipping_charges: ConfidenceField = Field(default_factory=missing_confidence_field)
    freight_charges: ConfidenceField = Field(default_factory=missing_confidence_field)
    handling_charges: ConfidenceField = Field(default_factory=missing_confidence_field)
    insurance_charges: ConfidenceField = Field(default_factory=missing_confidence_field)
    packaging_charges: ConfidenceField = Field(default_factory=missing_confidence_field)
    other_charges: List[OtherCharge] = Field(default_factory=list)
    grand_total: ConfidenceField = Field(default_factory=missing_confidence_field)

    line_items: List[LineItem] = Field(default_factory=list)
