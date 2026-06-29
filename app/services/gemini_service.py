import json
import pathlib

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, MODEL_NAME
from app.schemas.invoice import InvoiceData
from app.services.pdf_parser import PDFParser


class GeminiService:

    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    # -----------------------------------------------------
    # Shared Prompt
    # -----------------------------------------------------

    def _invoice_prompt(self):

        return """
You are an Accounts Payable Invoice Extraction AI.

Extract every invoice field accurately.

Rules:

- Never invent values.
- Extract only values explicitly visible on the invoice.
- Do not calculate values yourself.
- Return {"value": null, "confidence": 0} for any missing field.
- Preserve confidence scores for every extracted field.
- Confidence between 0 and 1.
- Never assume tax is zero simply because another charge exists.
- If tax is not present, return {"value": null, "confidence": 0}.
- If shipping charges are present, extract the amount.
- If a discount percentage is explicitly mentioned, extract both discount_percentage and discount_amount only if both values are explicitly visible on the invoice.
- Extract every additional visible charge. Use the named charge fields for shipping, freight, handling, insurance, and packaging. Put all remaining charges in other_charges with their visible name and amount.
- If multiple additional charges exist, extract every one.
- Ensure subtotal - discount + shipping + tax + other charges = grand_total whenever those values are explicitly present on the invoice. If the visible values do not reconcile, still return the visible values and do not invent a balancing amount.

Confidence Guide

0.99 = Explicit
0.95 = Highly Certain
0.85 = Clear from label/context
0.60 = Guess
0.00 = Missing

Return ONLY valid JSON.

{
    "invoice_number":{
        "value":"",
        "confidence":0.0
    },
    "vendor_name":{
        "value":"",
        "confidence":0.0
    },
    "invoice_date":{
        "value":"",
        "confidence":0.0
    },
    "due_date":{
        "value":"",
        "confidence":0.0
    },
    "subtotal":{
        "value":null,
        "confidence":0.0
    },
    "discount_percentage":{
        "value":null,
        "confidence":0.0
    },
    "discount_amount":{
        "value":null,
        "confidence":0.0
    },
    "tax":{
        "value":null,
        "confidence":0.0
    },
    "shipping_charges":{
        "value":null,
        "confidence":0.0
    },
    "freight_charges":{
        "value":null,
        "confidence":0.0
    },
    "handling_charges":{
        "value":null,
        "confidence":0.0
    },
    "insurance_charges":{
        "value":null,
        "confidence":0.0
    },
    "packaging_charges":{
        "value":null,
        "confidence":0.0
    },
    "other_charges":[
        {
            "name":{
                "value":"",
                "confidence":0.0
            },
            "amount":{
                "value":null,
                "confidence":0.0
            }
        }
    ],
    "grand_total":{
        "value":null,
        "confidence":0.0
    },
    "line_items":[
        {
            "description":{
                "value":"",
                "confidence":0.0
            },
            "quantity":{
                "value":0,
                "confidence":0.0
            },
            "unit_price":{
                "value":0,
                "confidence":0.0
            },
            "total":{
                "value":0,
                "confidence":0.0
            }
        }
    ]
}
"""

    # -----------------------------------------------------
    # TEXT
    # -----------------------------------------------------

    def extract_from_text(self, text: str) -> InvoiceData:

        prompt = self._invoice_prompt() + "\n\nInvoice:\n\n" + text

        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )

        return InvoiceData(**json.loads(response.text))

    # -----------------------------------------------------
    # IMAGE / PDF VISION
    # -----------------------------------------------------

    def extract_from_file(self, file_path: str) -> InvoiceData:

        uploaded = self.client.files.upload(
            file=pathlib.Path(file_path)
        )

        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                uploaded,
                self._invoice_prompt()
            ],
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )

        return InvoiceData(**json.loads(response.text))

    # -----------------------------------------------------
    # SMART ENTRY POINT
    # -----------------------------------------------------

    def extract_invoice(self, input_path: str) -> InvoiceData:

        path = pathlib.Path(input_path)

        if not path.exists():
            raise FileNotFoundError(f"{input_path} does not exist.")

        extension = path.suffix.lower()

        if extension == ".pdf":

            text = PDFParser.extract_text(input_path)

            if text.strip():

                print("Using pdfplumber")

                return self.extract_from_text(text)

            print("Scanned PDF detected.")
            print("Using Gemini Vision...")

            return self.extract_from_file(input_path)

        elif extension in [".png", ".jpg", ".jpeg", ".webp"]:

            print("Image detected.")
            print("Using Gemini Vision...")

            return self.extract_from_file(input_path)

        else:
            raise ValueError(
                f"Unsupported file type: {extension}"
            )
