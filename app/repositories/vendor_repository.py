from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models import PendingVendor, Vendor


def normalize_vendor_key(value: str) -> str:
    return " ".join(value.casefold().split())


class VendorRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_vendors(self) -> list[Vendor]:
        return self.db.query(Vendor).order_by(Vendor.vendor_name.asc()).all()

    def list_pending_vendors(self) -> list[PendingVendor]:
        return (
            self.db.query(PendingVendor)
            .order_by(PendingVendor.id.asc())
            .all()
        )

    def get_vendor_by_name(self, vendor_name: str) -> Vendor | None:
        key = normalize_vendor_key(vendor_name)
        return (
            self.db.query(Vendor)
            .filter(func.lower(func.trim(Vendor.vendor_name)) == key)
            .first()
        )

    def get_pending_by_name(self, vendor_name: str) -> PendingVendor | None:
        key = normalize_vendor_key(vendor_name)
        return (
            self.db.query(PendingVendor)
            .filter(func.lower(func.trim(PendingVendor.vendor_name)) == key)
            .first()
        )

    def vendor_exists(self, vendor_name: str) -> bool:
        return self.get_vendor_by_name(vendor_name) is not None

    def pending_exists(self, vendor_name: str) -> bool:
        return self.get_pending_by_name(vendor_name) is not None

    def add_pending_vendor(
        self,
        vendor_name: str,
        *,
        email: str | None = None,
        country: str | None = None,
        status: str = "Pending",
    ) -> PendingVendor:
        existing_pending = self.get_pending_by_name(vendor_name)
        if existing_pending is not None:
            return existing_pending

        pending = PendingVendor(
            vendor_name=vendor_name.strip(),
            email=email,
            country=country,
            status=status,
        )

        try:
            self.db.add(pending)
            self.db.flush()
            return pending
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def add_vendor(
        self,
        vendor_name: str,
        *,
        canonical_name: str,
        email: str | None = None,
        country: str | None = None,
    ) -> Vendor:
        existing = self.get_vendor_by_name(vendor_name)
        if existing is not None:
            return existing

        vendor = Vendor(
            vendor_name=vendor_name.strip(),
            canonical_name=canonical_name.strip(),
            email=email,
            country=country,
        )

        try:
            self.db.add(vendor)
            self.db.flush()
            return vendor
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def delete_pending_vendor(self, pending_vendor: PendingVendor) -> None:
        try:
            self.db.delete(pending_vendor)
            self.db.flush()
        except SQLAlchemyError:
            self.db.rollback()
            raise

