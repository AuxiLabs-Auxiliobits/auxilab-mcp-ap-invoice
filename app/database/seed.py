from sqlalchemy.orm import Session

from app.database.database import Base, SessionLocal, engine
from app.database.models import Vendor


# Create all tables
Base.metadata.create_all(bind=engine)


def seed_vendors():
    db: Session = SessionLocal()

    # Don't insert data again if vendors already exist
    if db.query(Vendor).count() > 0:
        print("Vendor database already seeded.")
        db.close()
        return

    vendors = [
        Vendor(vendor_name="Microsoft", canonical_name="Microsoft Corporation", email="accounts@microsoft.com", country="USA"),
        Vendor(vendor_name="Microsoft Corporation", canonical_name="Microsoft Corporation", email="accounts@microsoft.com", country="USA"),
        Vendor(vendor_name="Microsoft Corp.", canonical_name="Microsoft Corporation", email="accounts@microsoft.com", country="USA"),
        Vendor(vendor_name="MSFT Corp.", canonical_name="Microsoft Corporation", email="accounts@microsoft.com", country="USA"),
        Vendor(vendor_name="Microsoft Ltd", canonical_name="Microsoft Corporation", email="accounts@microsoft.com", country="USA"),
        Vendor(vendor_name="Microsoft Pvt Ltd", canonical_name="Microsoft Corporation", email="accounts@microsoft.com", country="USA"),

        Vendor(vendor_name="Google", canonical_name="Google LLC", email="payments@google.com", country="USA"),
        Vendor(vendor_name="Google LLC", canonical_name="Google LLC", email="payments@google.com", country="USA"),
        Vendor(vendor_name="Google Inc.", canonical_name="Google LLC", email="payments@google.com", country="USA"),
        Vendor(vendor_name="Google Corporation", canonical_name="Google LLC", email="payments@google.com", country="USA"),

        Vendor(vendor_name="Amazon", canonical_name="Amazon Inc.", email="finance@amazon.com", country="USA"),
        Vendor(vendor_name="Amazon Inc.", canonical_name="Amazon Inc.", email="finance@amazon.com", country="USA"),
        Vendor(vendor_name="Amazon India", canonical_name="Amazon Inc.", email="finance@amazon.com", country="India"),
        Vendor(vendor_name="Amazon Web Services", canonical_name="Amazon Inc.", email="finance@amazon.com", country="USA"),
        Vendor(vendor_name="AWS", canonical_name="Amazon Inc.", email="finance@amazon.com", country="USA"),

        Vendor(vendor_name="Infosys", canonical_name="Infosys Limited", email="finance@infosys.com", country="India"),
        Vendor(vendor_name="Infosys Limited", canonical_name="Infosys Limited", email="finance@infosys.com", country="India"),
        Vendor(vendor_name="Infosys Ltd", canonical_name="Infosys Limited", email="finance@infosys.com", country="India"),
        Vendor(vendor_name="Infosys BPO Ltd", canonical_name="Infosys Limited", email="finance@infosys.com", country="India"),
        Vendor(vendor_name="Infosys Pvt Ltd", canonical_name="Infosys Limited", email="finance@infosys.com", country="India"),
       
        Vendor(vendor_name="TCS", canonical_name="Tata Consultancy Services", email="finance@tcs.com", country="India"),

        Vendor(vendor_name="Wipro", canonical_name="Wipro Limited", email="finance@wipro.com", country="India"),

        Vendor(vendor_name="IBM", canonical_name="IBM Corporation", email="finance@ibm.com", country="USA"),

        Vendor(vendor_name="Oracle", canonical_name="Oracle Corporation", email="finance@oracle.com", country="USA"),

        Vendor(vendor_name="Adobe", canonical_name="Adobe Inc.", email="finance@adobe.com", country="USA"),

        Vendor(vendor_name="SAP", canonical_name="SAP SE", email="finance@sap.com", country="Germany"),

        Vendor(vendor_name="Capgemini", canonical_name="Capgemini SE", email="finance@capgemini.com", country="France"),

        Vendor(vendor_name="Accenture", canonical_name="Accenture PLC", email="finance@accenture.com", country="Ireland"),

        Vendor(vendor_name="HCL", canonical_name="HCL Technologies", email="finance@hcl.com", country="India"),

        Vendor(vendor_name="Cognizant", canonical_name="Cognizant Technology Solutions", email="finance@cognizant.com", country="USA"),

        Vendor(vendor_name="Dell", canonical_name="Dell Technologies", email="finance@dell.com", country="USA"),
        Vendor(vendor_name="Dell Technologies", canonical_name="Dell Technologies", email="finance@dell.com", country="USA"),
        Vendor(vendor_name="Dell Inc.", canonical_name="Dell Technologies", email="finance@dell.com", country="USA"),

        Vendor(vendor_name="HP", canonical_name="HP Inc.", email="finance@hp.com", country="USA"),

        Vendor(vendor_name="Lenovo", canonical_name="Lenovo Group", email="finance@lenovo.com", country="China"),

        Vendor(vendor_name="Cisco", canonical_name="Cisco Systems", email="finance@cisco.com", country="USA"),

        Vendor(vendor_name="Intel", canonical_name="Intel Corporation", email="finance@intel.com", country="USA"),

        Vendor(vendor_name="NVIDIA", canonical_name="NVIDIA Corporation", email="finance@nvidia.com", country="USA"),

        Vendor(vendor_name="AMD", canonical_name="Advanced Micro Devices", email="finance@amd.com", country="USA"),

        Vendor(vendor_name="PayPal", canonical_name="PayPal Holdings", email="finance@paypal.com", country="USA"),

        Vendor(vendor_name="Stripe", canonical_name="Stripe Inc.", email="finance@stripe.com", country="USA"),

        Vendor(vendor_name="Salesforce", canonical_name="Salesforce Inc.", email="finance@salesforce.com", country="USA"),

        Vendor(vendor_name="Zoho", canonical_name="Zoho Corporation", email="finance@zoho.com", country="India"),
    ]

    db.add_all(vendors)
    db.commit()

    print(f"Inserted {len(vendors)} vendors successfully.")

    db.close()


if __name__ == "__main__":
    seed_vendors()
