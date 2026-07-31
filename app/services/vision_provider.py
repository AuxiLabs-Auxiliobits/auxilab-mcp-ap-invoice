from __future__ import annotations

import base64
import json
import os
import re
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import Iterable

import pdfplumber

from app.config import (
    ANTHROPIC_MODEL_NAME,
    GEMINI_MODEL_NAME,
    OPENAI_MODEL_NAME,
    VISION_PROVIDER,
)
from app.schemas.invoice import InvoiceData


VISION_PROMPT = """
You are an Accounts Payable invoice extraction engine.

Return ONLY valid JSON matching this schema:

{
  "invoice_number": {"value": null, "confidence": 0.0},
  "vendor_name": {"value": null, "confidence": 0.0},
  "invoice_date": {"value": null, "confidence": 0.0},
  "due_date": {"value": null, "confidence": 0.0},
  "subtotal": {"value": null, "confidence": 0.0},
  "discount_percentage": {"value": null, "confidence": 0.0},
  "discount_amount": {"value": null, "confidence": 0.0},
  "tax": {"value": null, "confidence": 0.0},
  "shipping_charges": {"value": null, "confidence": 0.0},
  "freight_charges": {"value": null, "confidence": 0.0},
  "handling_charges": {"value": null, "confidence": 0.0},
  "insurance_charges": {"value": null, "confidence": 0.0},
  "packaging_charges": {"value": null, "confidence": 0.0},
  "other_charges": [],
  "grand_total": {"value": null, "confidence": 0.0},
  "line_items": []
}

Rules:
- Never invent values.
- Use only values visible on the invoice.
- Return null for any missing field.
- Keep confidence between 0 and 1.
- Do not add commentary or markdown.
""".strip()

NO_VISION_PROVIDER_MESSAGE = (
    "No vision provider configured. Text-based invoices work without any API key. "
    "Configure Gemini/OpenAI/Anthropic to process scanned invoices."
)


class VisionProvider(ABC):
    """Abstract provider interface for invoice vision extraction."""

    def extract_invoice(self, input_path: str) -> InvoiceData:
        path = Path(input_path)

        if path.suffix.lower() == ".pdf":
            return self.extract_from_scanned_pdf(input_path)

        return self.extract_from_image(input_path)

    @abstractmethod
    def extract_from_image(self, input_path: str) -> InvoiceData:
        raise NotImplementedError

    @abstractmethod
    def extract_from_scanned_pdf(self, input_path: str) -> InvoiceData:
        raise NotImplementedError

    def _build_image_parts_from_file(self, input_path: str) -> list[tuple[str, bytes]]:
        path = Path(input_path)
        return [(self._guess_mime_type(path), path.read_bytes())]

    def _build_image_parts_from_scanned_pdf(
        self,
        input_path: str,
    ) -> list[tuple[str, bytes]]:
        path = Path(input_path)
        image_parts: list[tuple[str, bytes]] = []

        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_image = page.to_image(resolution=200).original.convert("RGB")
                buffer = BytesIO()
                page_image.save(buffer, format="PNG")
                image_parts.append(("image/png", buffer.getvalue()))

        return image_parts

    def _parse_invoice_json(self, response_text: str) -> InvoiceData:
        cleaned = response_text.strip()

        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]

        return InvoiceData(**json.loads(cleaned))

    def _guess_mime_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix, "application/octet-stream")

    def _ensure_file_exists(self, input_path: str) -> Path:
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"{input_path} does not exist.")
        return path


class NullVisionProvider(VisionProvider):
    def extract_from_image(self, input_path: str) -> InvoiceData:
        self._ensure_file_exists(input_path)
        raise RuntimeError(NO_VISION_PROVIDER_MESSAGE)

    def extract_from_scanned_pdf(self, input_path: str) -> InvoiceData:
        self._ensure_file_exists(input_path)
        raise RuntimeError(NO_VISION_PROVIDER_MESSAGE)


class GeminiProvider(VisionProvider):
    def extract_from_image(self, input_path: str) -> InvoiceData:
        path = self._ensure_file_exists(input_path)
        return self._extract_from_image_parts(self._build_image_parts_from_file(str(path)))

    def extract_from_scanned_pdf(self, input_path: str) -> InvoiceData:
        path = self._ensure_file_exists(input_path)
        return self._extract_from_image_parts(
            self._build_image_parts_from_scanned_pdf(str(path))
        )

    def _extract_from_image_parts(
        self,
        image_parts: list[tuple[str, bytes]],
    ) -> InvoiceData:
        response_text = self._invoke(VISION_PROMPT, image_parts)
        return self._parse_invoice_json(response_text)

    def _invoke(self, prompt: str, image_parts: list[tuple[str, bytes]]) -> str:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "Gemini vision provider requires the google-genai package."
            ) from exc

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini vision extraction.")

        client = genai.Client(api_key=api_key)
        contents = [prompt]
        for mime_type, data in image_parts:
            contents.append(types.Part.from_bytes(data=data, mime_type=mime_type))

        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL_NAME", GEMINI_MODEL_NAME),
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )

        return response.text or ""


class OpenAIProvider(VisionProvider):
    def extract_from_image(self, input_path: str) -> InvoiceData:
        path = self._ensure_file_exists(input_path)
        return self._extract_from_image_parts(self._build_image_parts_from_file(str(path)))

    def extract_from_scanned_pdf(self, input_path: str) -> InvoiceData:
        path = self._ensure_file_exists(input_path)
        return self._extract_from_image_parts(
            self._build_image_parts_from_scanned_pdf(str(path))
        )

    def _extract_from_image_parts(
        self,
        image_parts: list[tuple[str, bytes]],
    ) -> InvoiceData:
        response_text = self._invoke(VISION_PROMPT, image_parts)
        return self._parse_invoice_json(response_text)

    def _invoke(self, prompt: str, image_parts: list[tuple[str, bytes]]) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI vision provider requires the openai package."
            ) from exc

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI vision extraction.")

        content = [{"type": "text", "text": prompt}]
        for mime_type, data in image_parts:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64.b64encode(data).decode('utf-8')}"
                    },
                }
            )

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL_NAME", OPENAI_MODEL_NAME),
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": content}],
        )

        return response.choices[0].message.content or ""


class AnthropicProvider(VisionProvider):
    def extract_from_image(self, input_path: str) -> InvoiceData:
        path = self._ensure_file_exists(input_path)
        return self._extract_from_image_parts(self._build_image_parts_from_file(str(path)))

    def extract_from_scanned_pdf(self, input_path: str) -> InvoiceData:
        path = self._ensure_file_exists(input_path)
        return self._extract_from_image_parts(
            self._build_image_parts_from_scanned_pdf(str(path))
        )

    def _extract_from_image_parts(
        self,
        image_parts: list[tuple[str, bytes]],
    ) -> InvoiceData:
        response_text = self._invoke(VISION_PROMPT, image_parts)
        return self._parse_invoice_json(response_text)

    def _invoke(self, prompt: str, image_parts: list[tuple[str, bytes]]) -> str:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError(
                "Anthropic vision provider requires the anthropic package."
            ) from exc

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is required for Anthropic vision extraction."
            )

        content = [{"type": "text", "text": prompt}]
        for mime_type, data in image_parts:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": base64.b64encode(data).decode("utf-8"),
                    },
                }
            )

        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL_NAME", ANTHROPIC_MODEL_NAME),
            max_tokens=4096,
            temperature=0,
            messages=[{"role": "user", "content": content}],
        )

        return "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        )


class VisionProviderFactory:
    @staticmethod
    def create(provider_name: str | None = None) -> VisionProvider:
        provider = (provider_name or VISION_PROVIDER or "gemini").strip().lower()

        if provider in {"", "none"}:
            return NullVisionProvider()

        if provider == "gemini":
            return GeminiProvider()

        if provider == "openai":
            return OpenAIProvider()

        if provider == "anthropic":
            return AnthropicProvider()

        raise ValueError("VISION_PROVIDER must be one of: gemini, openai, anthropic, none")


# Backward-compatible aliases for earlier imports.
GeminiVisionProvider = GeminiProvider
OpenAIVisionProvider = OpenAIProvider
AnthropicVisionProvider = AnthropicProvider
