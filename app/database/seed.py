from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.bootstrap import initialize_database
from app.database.database import SessionLocal
from app.database.models import Vendor
from app.repositories.vendor_repository import VendorRepository


logger = get_logger(__name__)


SEED_VENDORS: list[tuple[str, str, str, str]] = [
    ("Microsoft", "Microsoft Corporation", "accounts@microsoft.com", "USA"),
    ("Microsoft Corporation", "Microsoft Corporation", "accounts@microsoft.com", "USA"),
    ("Microsoft Corp.", "Microsoft Corporation", "accounts@microsoft.com", "USA"),
    ("MSFT Corp.", "Microsoft Corporation", "accounts@microsoft.com", "USA"),
    ("Microsoft Ltd", "Microsoft Corporation", "accounts@microsoft.com", "USA"),
    ("Microsoft Pvt Ltd", "Microsoft Corporation", "accounts@microsoft.com", "USA"),
    ("Google", "Google LLC", "payments@google.com", "USA"),
    ("Google LLC", "Google LLC", "payments@google.com", "USA"),
    ("Google Inc.", "Google LLC", "payments@google.com", "USA"),
    ("Google Corporation", "Google LLC", "payments@google.com", "USA"),
    ("Amazon", "Amazon Inc.", "finance@amazon.com", "USA"),
    ("Amazon Inc.", "Amazon Inc.", "finance@amazon.com", "USA"),
    ("Amazon India", "Amazon Inc.", "finance@amazon.com", "India"),
    ("Amazon Web Services", "Amazon Inc.", "finance@amazon.com", "USA"),
    ("AWS", "Amazon Inc.", "finance@amazon.com", "USA"),
    ("Infosys", "Infosys Limited", "finance@infosys.com", "India"),
    ("Infosys Limited", "Infosys Limited", "finance@infosys.com", "India"),
    ("Infosys Ltd", "Infosys Limited", "finance@infosys.com", "India"),
    ("Infosys BPO Ltd", "Infosys Limited", "finance@infosys.com", "India"),
    ("Infosys Pvt Ltd", "Infosys Limited", "finance@infosys.com", "India"),
    ("TCS", "Tata Consultancy Services", "finance@tcs.com", "India"),
    ("Wipro", "Wipro Limited", "finance@wipro.com", "India"),
    ("IBM", "IBM Corporation", "finance@ibm.com", "USA"),
    ("Oracle", "Oracle Corporation", "finance@oracle.com", "USA"),
    ("Adobe", "Adobe Inc.", "finance@adobe.com", "USA"),
    ("SAP", "SAP SE", "finance@sap.com", "Germany"),
    ("Capgemini", "Capgemini SE", "finance@capgemini.com", "France"),
    ("Accenture", "Accenture PLC", "finance@accenture.com", "Ireland"),
    ("HCL", "HCL Technologies", "finance@hcl.com", "India"),
    ("Cognizant", "Cognizant Technology Solutions", "finance@cognizant.com", "USA"),
    ("Dell", "Dell Technologies", "finance@dell.com", "USA"),
    ("Dell Technologies", "Dell Technologies", "finance@dell.com", "USA"),
    ("Dell Inc.", "Dell Technologies", "finance@dell.com", "USA"),
    ("HP", "HP Inc.", "finance@hp.com", "USA"),
    ("Lenovo", "Lenovo Group", "finance@lenovo.com", "China"),
    ("Cisco", "Cisco Systems", "finance@cisco.com", "USA"),
    ("Intel", "Intel Corporation", "finance@intel.com", "USA"),
    ("NVIDIA", "NVIDIA Corporation", "finance@nvidia.com", "USA"),
    ("AMD", "Advanced Micro Devices", "finance@amd.com", "USA"),
    ("PayPal", "PayPal Holdings", "finance@paypal.com", "USA"),
    ("Stripe", "Stripe Inc.", "finance@stripe.com", "USA"),
    ("Salesforce", "Salesforce Inc.", "finance@salesforce.com", "USA"),
    ("Zoho", "Zoho Corporation", "finance@zoho.com", "India"),
]


def seed_vendors() -> None:
    initialize_database()

    db: Session = SessionLocal()
    repository = VendorRepository(db)
    inserted_count = 0

    try:
        for vendor_name, canonical_name, email, country in SEED_VENDORS:
            if repository.get_vendor_by_name(vendor_name) is not None:
                continue

            db.add(
                Vendor(
                    vendor_name=vendor_name,
                    canonical_name=canonical_name,
                    email=email,
                    country=country,
                )
            )
            inserted_count += 1

        db.commit()
        logger.info(
            "Vendor seed completed",
            extra={"inserted_count": inserted_count},
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed_vendors()

