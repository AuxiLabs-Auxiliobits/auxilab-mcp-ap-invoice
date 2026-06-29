from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.models import PendingVendor
from app.repositories.vendor_repository import VendorRepository


logger = get_logger(__name__)


class VendorOnboarding:
    def __init__(self, db: Session):
        self.db = db
        self.repository = VendorRepository(db)

    def queue_vendor(
        self,
        vendor_name: str,
        email: str | None = None,
        country: str | None = None,
    ) -> dict[str, Any]:
        normalized_name = vendor_name.strip()
        if not normalized_name:
            raise ValueError("vendor_name must be provided")

        if self.repository.vendor_exists(normalized_name):
            return {
                "status": "Already Approved",
                "vendor": normalized_name,
                "queued": False,
            }

        existing_pending = self.repository.get_pending_by_name(normalized_name)
        if existing_pending is not None:
            return {
                "status": "Already Pending",
                "vendor": existing_pending.vendor_name,
                "pending_vendor_id": existing_pending.id,
                "queued": False,
            }

        try:
            pending = self.repository.add_pending_vendor(
                normalized_name,
                email=email,
                country=country,
            )
            self.db.commit()
            logger.info(
                "Vendor queued for approval",
                extra={"vendor_name": normalized_name, "pending_vendor_id": pending.id},
            )
            return {
                "status": "Added To Pending Vendors",
                "vendor": pending.vendor_name,
                "pending_vendor_id": pending.id,
                "queued": True,
            }
        except SQLAlchemyError:
            self.db.rollback()
            logger.exception("Failed to queue vendor", extra={"vendor_name": normalized_name})
            raise

    def list_pending(self) -> list[dict[str, Any]]:
        pending = self.repository.list_pending_vendors()
        return [
            {
                "id": vendor.id,
                "vendor_name": vendor.vendor_name,
                "email": vendor.email,
                "country": vendor.country,
                "status": vendor.status,
            }
            for vendor in pending
        ]

    def approve(self, vendor_id: int, confirm: bool) -> dict[str, Any]:
        if not confirm:
            return {"status": "Cancelled", "approved": False}

        pending = (
            self.db.query(PendingVendor)
            .filter(PendingVendor.id == vendor_id)
            .first()
        )

        if pending is None:
            return {
                "status": "Vendor Not Found",
                "approved": False,
            }

        try:
            existing_vendor = self.repository.get_vendor_by_name(pending.vendor_name)
            if existing_vendor is not None:
                self.repository.delete_pending_vendor(pending)
                self.db.commit()
                return {
                    "status": "Already Approved",
                    "approved": False,
                    "vendor": existing_vendor.vendor_name,
                    "vendor_id": existing_vendor.id,
                }

            vendor = self.repository.add_vendor(
                pending.vendor_name,
                canonical_name=pending.vendor_name,
                email=pending.email,
                country=pending.country,
            )
            self.repository.delete_pending_vendor(pending)
            self.db.commit()

            logger.info(
                "Pending vendor approved",
                extra={"vendor_name": vendor.vendor_name, "vendor_id": vendor.id},
            )

            return {
                "status": "Approved",
                "approved": True,
                "vendor": vendor.vendor_name,
                "vendor_id": vendor.id,
            }
        except SQLAlchemyError:
            self.db.rollback()
            logger.exception("Failed to approve vendor", extra={"vendor_id": vendor_id})
            raise

    def reject(self, vendor_id: int, confirm: bool) -> dict[str, Any]:
        if not confirm:
            return {"status": "Cancelled", "rejected": False}

        pending = (
            self.db.query(PendingVendor)
            .filter(PendingVendor.id == vendor_id)
            .first()
        )

        if pending is None:
            return {
                "status": "Vendor Not Found",
                "rejected": False,
            }

        try:
            self.repository.delete_pending_vendor(pending)
            self.db.commit()
            logger.info(
                "Pending vendor rejected",
                extra={"vendor_name": pending.vendor_name, "vendor_id": vendor_id},
            )
            return {
                "status": "Rejected",
                "rejected": True,
            }
        except SQLAlchemyError:
            self.db.rollback()
            logger.exception("Failed to reject vendor", extra={"vendor_id": vendor_id})
            raise

