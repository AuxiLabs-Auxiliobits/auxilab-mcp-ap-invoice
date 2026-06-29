import pdfplumber


class PDFParser:
    """
    Extracts raw text from invoice PDFs.
    """

    @staticmethod
    def extract_text(pdf_path: str) -> str:
        """
        Extract text from every page of a PDF.

        Args:
            pdf_path (str): Path to PDF file.

        Returns:
            str: Complete extracted text.
        """

        extracted_text = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()

                if text:
                    extracted_text.append(text)

        return "\n".join(extracted_text).strip()