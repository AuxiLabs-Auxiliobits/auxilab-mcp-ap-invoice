from __future__ import annotations

from pathlib import Path

from app.schemas.invoice import InvoiceData
from app.services.local_invoice_extractor import LocalInvoiceExtractor
from app.services.pdf_parser import PDFParser
from app.services.vision_provider import VisionProviderFactory


class ExtractionRouter:
    """
    Routes invoice files to the local parser or a vision provider.
    """

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

    def __init__(self, provider_name: str | None = None):
        self.local_extractor = LocalInvoiceExtractor()
        self.vision_provider = VisionProviderFactory.create(provider_name)

    def extract_invoice(self, input_path: str) -> InvoiceData:
        path = Path(input_path)

        if not path.exists():
            raise FileNotFoundError(f"{input_path} does not exist.")

        suffix = path.suffix.lower()

        if suffix == ".pdf":
            text = PDFParser.extract_text(input_path)
            if text.strip():
                return self.local_extractor.extract_from_text(text)
            return self.vision_provider.extract_from_scanned_pdf(input_path)

        if suffix in self.IMAGE_EXTENSIONS:
            return self.vision_provider.extract_from_image(input_path)

        raise ValueError(f"Unsupported file type: {suffix}")
