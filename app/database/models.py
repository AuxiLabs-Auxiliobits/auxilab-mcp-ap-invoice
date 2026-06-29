from sqlalchemy import Column, Integer, String, Float

from app.database.database import Base


class Vendor(Base):
    """
    Vendor Master Table
    Used by Vendor Normalizer
    """

    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)

    vendor_name = Column(String, unique=True, nullable=False)

    canonical_name = Column(String, nullable=False)

    email = Column(String)

    country = Column(String)


class ProcessedInvoice(Base):
    """
    Stores processed invoices.
    """

    __tablename__ = "processed_invoices"

    id = Column(Integer, primary_key=True, index=True)

    invoice_number = Column(String, index=True, nullable=False)

    vendor_name = Column(String, nullable=False)

    invoice_date = Column(String)

    due_date = Column(String)

    subtotal = Column(Float)

    tax = Column(Float)

    grand_total = Column(Float)

    status = Column(String, default="Processed")