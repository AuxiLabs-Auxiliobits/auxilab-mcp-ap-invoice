from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger
from app.database.database import Base, engine

logger = get_logger(__name__)


def initialize_database() -> None:
    """Create tables and safety indexes for the SQLite database."""

    try:
        import app.database.models  # noqa: F401

        Base.metadata.create_all(bind=engine)

        with engine.begin() as connection:
            existing_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(processed_invoices)"))
            }
            for column_name, column_sql in (
                ("discount_percentage", "FLOAT"),
                ("shipping_charges", "FLOAT"),
                ("freight_charges", "FLOAT"),
                ("handling_charges", "FLOAT"),
                ("insurance_charges", "FLOAT"),
                ("packaging_charges", "FLOAT"),
                ("other_charges_json", "TEXT"),
            ):
                if column_name not in existing_columns:
                    connection.execute(
                        text(
                            f"ALTER TABLE processed_invoices ADD COLUMN {column_name} {column_sql}"
                        )
                    )

            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_vendors_vendor_name_nocase "
                    "ON vendors (LOWER(TRIM(vendor_name)))"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_pending_vendors_vendor_name_nocase "
                    "ON pending_vendors (LOWER(TRIM(vendor_name)))"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_processed_invoices_invoice_number_nocase "
                    "ON processed_invoices (LOWER(TRIM(invoice_number)))"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_processed_invoices_vendor_name "
                    "ON processed_invoices (vendor_name)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_pending_vendors_vendor_name "
                    "ON pending_vendors (vendor_name)"
                )
            )

        logger.info("Database initialized", extra={"database_url": str(engine.url)})
    except SQLAlchemyError:
        logger.exception("Database initialization failed")
        raise
