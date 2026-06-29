from __future__ import annotations

from typing import Any

from app.schemas.invoice import InvoiceData


class CompletenessChecker:
    """
    Checks whether all mandatory invoice fields are present.
    """

    REQUIRED_FIELDS = [
        "invoice_number",
        "vendor_name",
        "invoice_date",
        "due_date",
        "subtotal",
        "tax",
        "grand_total",
    ]

    def check(self, invoice: InvoiceData) -> dict[str, Any]:

        missing_fields = []

        for field in self.REQUIRED_FIELDS:

            field_data = getattr(invoice, field)

            value = field_data.value

            if value is None:
                missing_fields.append(field)

            elif isinstance(value, str) and value.strip() == "":
                missing_fields.append(field)

        total_fields = len(self.REQUIRED_FIELDS)

        present_fields = total_fields - len(missing_fields)

        completeness_score = round(
            (present_fields / total_fields) * 100,
            2
        )

        if completeness_score == 100:
            action = "Process"

        elif completeness_score >= 70:
            action = "Hold"

        else:
            action = "Return to Vendor"

        return {
            "completeness_score": completeness_score,
            "missing_fields": missing_fields,
            "missing_count": len(missing_fields),
            "total_fields": total_fields,
            "present_count": present_fields,
            "recommended_action": action,
        }
