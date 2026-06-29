from sqlalchemy.orm import Session

from app.services.gemini_service import GeminiService
from app.tools.duplicate_detector import DuplicateDetector


class InvoiceProcessor:

    def __init__(self, db: Session):

        self.db = db
        self.gemini = GeminiService()
        self.detector = DuplicateDetector(db)

    def process(self, file_path: str):

        print("Extracting Invoice...")

        # GeminiService automatically decides:
        # PDF with text -> pdfplumber
        # Scanned PDF -> Gemini Vision
        # Image -> Gemini Vision
        invoice = self.gemini.extract_invoice(file_path)

        print("Checking Duplicate...")

        duplicate = self.detector.check_duplicate(invoice)

        if not duplicate["is_duplicate"]:

            print("Saving Invoice...")

            self.detector.save_invoice(invoice)

        return {
            "invoice": invoice.model_dump(),
            "duplicate": duplicate,
        }