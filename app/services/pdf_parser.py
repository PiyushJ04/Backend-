from __future__ import annotations

from app.core.config import settings
from app.services.ai.ocr import PDFOCR


class PDFParser:
    """Extract page-aware PDF text with OCR fallback for scanned pages."""

    @staticmethod
    def extract(pdf_bytes: bytes) -> str:
        return "\n\n".join(
            page_text for _, page_text in PDFParser.extract_pages(pdf_bytes)
        )

    @staticmethod
    def extract_pages(pdf_bytes: bytes) -> list[tuple[int, str]]:
        """Return `(page_number, text)` with OCR fallback for scanned pages."""
        return PDFOCR(
            language=settings.ocr_language,
            dpi=settings.ocr_dpi,
            min_native_chars=settings.ocr_min_native_chars,
            min_native_words=settings.ocr_min_native_words,
        ).extract_pages(pdf_bytes)
