from app.services.extraction_router import ExtractionRouter


class GeminiService:
    """
    Backward-compatible compatibility wrapper around the extraction router.
    """

    def __init__(self, provider_name: str | None = None):
        self.router = ExtractionRouter(provider_name)

    def extract_invoice(self, input_path: str):
        return self.router.extract_invoice(input_path)
