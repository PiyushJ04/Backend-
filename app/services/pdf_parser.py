from __future__ import annotations

import threading

from app.core.config import settings
from app.services.ai.ocr import PDFOCR


class PDFParser:
    """Extract page-aware PDF text with OCR fallback for scanned pages.

    A single PDFOCR instance is reused for the lifetime of this process.
    This prevents PaddleOCR/PaddleX from being initialized repeatedly.
    """

    _ocr: PDFOCR | None = None
    _ocr_lock = threading.Lock()

    @classmethod
    def _get_ocr(cls) -> PDFOCR:
        if cls._ocr is None:
            with cls._ocr_lock:
                if cls._ocr is None:
                    cls._ocr = PDFOCR(
                        language=settings.ocr_language,
                        dpi=settings.ocr_dpi,
                        min_native_chars=settings.ocr_min_native_chars,
                        min_native_words=settings.ocr_min_native_words,
                    )
        return cls._ocr

    @classmethod
    def extract(cls, pdf_bytes: bytes) -> str:
        return "\n\n".join(
            page_text for _, page_text in cls.extract_pages(pdf_bytes)
        )

    @classmethod
    def extract_pages(cls, pdf_bytes: bytes) -> list[tuple[int, str]]:
        """Return `(page_number, text)` with OCR fallback for scanned pages."""
        return cls._get_ocr().extract_pages(pdf_bytes)