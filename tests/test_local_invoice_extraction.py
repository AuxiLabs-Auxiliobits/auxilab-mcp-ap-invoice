from __future__ import annotations

from app.services.gemini_service import GeminiService


def test_local_text_extraction_parses_common_invoice_fields() -> None:
    text = """
SuperStore INVOICE
# 23466
Date: Oct 05 2012
Bill To: Ship To:
Ship Mode: Standard Class
Todd Sumrall Visakhapatnam,
Andhra Pradesh,
Balance Due: $8,579.17
India
Item Quantity Rate Amount
Breville Refrigerator, Red 4 $2,077.32 $8,309.28
Appliances, Office Supplies, OFF-AP-3575
Subtotal: $8,309.28
Shipping: $269.89
Total: $8,579.17
Notes:
Thanks for your business!
Terms:
Order ID : IN-2012-TS2137058-41187
""".strip()

    invoice = GeminiService().extract_from_text(text)

    assert invoice.invoice_number.value == "23466"
    assert invoice.vendor_name.value == "SuperStore"
    assert invoice.subtotal.value == 8309.28
    assert invoice.shipping_charges.value == 269.89
    assert invoice.grand_total.value == 8579.17
    assert invoice.order_id.value == "IN-2012-TS2137058-41187"
    assert invoice.line_items[0].description.value == "Breville Refrigerator, Red"
