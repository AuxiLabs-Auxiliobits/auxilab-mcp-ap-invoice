from __future__ import annotations

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vendor_name: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)


class PendingVendor(Base):
    __tablename__ = "pending_vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vendor_name: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="Pending")


class ProcessedInvoice(Base):
    __tablename__ = "processed_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_number: Mapped[str] = mapped_column(
        String, index=True, nullable=False, unique=True
    )
    vendor_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    invoice_date: Mapped[str | None] = mapped_column(String, nullable=True)
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)
    subtotal: Mapped[float | None] = mapped_column(Float, nullable=True)
    tax: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_amount: Mapped[float | None] = mapped_column("discount", Float, nullable=True)
    shipping_charges: Mapped[float | None] = mapped_column(Float, nullable=True)
    freight_charges: Mapped[float | None] = mapped_column(Float, nullable=True)
    handling_charges: Mapped[float | None] = mapped_column(Float, nullable=True)
    insurance_charges: Mapped[float | None] = mapped_column(Float, nullable=True)
    packaging_charges: Mapped[float | None] = mapped_column(Float, nullable=True)
    other_charges_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    grand_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="Processed")
