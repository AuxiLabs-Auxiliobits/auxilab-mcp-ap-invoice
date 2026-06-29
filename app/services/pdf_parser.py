from __future__ import annotations

from pathlib import Path

import pdfplumber

from app.core.errors import app_error


class PDFParser:
    """
    Extracts raw text from invoice PDFs.
    """

    @staticmethod
    def extract_text(pdf_path: str | Path) -> str:
        """
        Extract text from every page of a PDF.

        Args:
            pdf_path (str): Path to PDF file.

        Returns:
            str: Complete extracted text.
        """

        path = Path(pdf_path).expanduser()
        if not path.exists():
            raise app_error(
                "FILE_NOT_FOUND",
                f"PDF file not found: {path}",
                step="extract_invoice",
                details={"path": str(path)},
            )

        extracted_text: list[str] = []

        try:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()

                    if text:
                        extracted_text.append(text)
        except Exception as exc:  # noqa: BLE001
            raise app_error(
                "PDF_PARSE_FAILED",
                f"Failed to parse PDF document: {path.name}",
                step="extract_invoice",
                details={"path": str(path)},
            ) from exc

        combined = "\n".join(extracted_text).strip()
        if not combined:
            raise app_error(
                "EMPTY_DOCUMENT",
                f"No readable text found in PDF document: {path.name}",
                step="extract_invoice",
                details={"path": str(path)},
            )

        return combined
