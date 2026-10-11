from __future__ import annotations

import logging
from typing import Any

import fitz
import numpy as np

logger = logging.getLogger(__name__)


class OCRError(RuntimeError):
    """Raised when OCR is required but cannot be completed."""


class PaddleOCRService:
    """Lazy PaddleOCR adapter for scanned academic PDFs.

    The adapter supports both the current PaddleOCR 3.x result format and
    the legacy `ocr()` result format so the application code remains stable.
    """

    def __init__(self, language: str = "en") -> None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise OCRError(
                "PaddleOCR is not installed. Install the OCR dependencies before "
                "processing scanned PDFs."
            ) from exc

        self._ocr = self._build_engine(PaddleOCR, language)

    @staticmethod
    def _build_engine(paddle_ocr_cls: Any, language: str) -> Any:
        try:
            return paddle_ocr_cls(
                lang=language,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        except TypeError:
            return paddle_ocr_cls(lang=language, use_angle_cls=True)

    def extract_text(self, image: np.ndarray) -> str:
        try:
            if hasattr(self._ocr, "predict"):
                result = self._ocr.predict(input=image)
                return self._extract_v3_result(result)
            result = self._ocr.ocr(image, cls=True)
            return self._extract_legacy_result(result)
        except Exception as exc:
            raise OCRError(f"PaddleOCR failed: {exc}") from exc

    @classmethod
    def _extract_v3_result(cls, result: Any) -> str:
        texts: list[str] = []
        if result is None:
            return ""

        if not isinstance(result, (list, tuple)):
            result = [result]

        for item in result:
            payload = getattr(item, "json", None)

            if callable(payload):
                payload = payload()

            if isinstance(payload, str):
                import json
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = None

            if isinstance(payload, dict):
                payload = payload.get("res", payload)
                rec_texts = payload.get("rec_texts", [])
                rec_scores = payload.get("rec_scores", [])
                for index, text in enumerate(rec_texts):
                    text = str(text).strip()
                    if not text:
                        continue
                    if rec_scores and index < len(rec_scores):
                        try:
                            if float(rec_scores[index]) < 0.30:
                                continue
                        except (TypeError, ValueError):
                            pass
                    texts.append(text)
                continue
            if isinstance(item, dict):
                payload = item.get("res", item)
                for text in payload.get("rec_texts", []):
                    text = str(text).strip()
                    if text:
                        texts.append(text)

        return "\n".join(texts).strip()

    @staticmethod
    def _extract_legacy_result(result: Any) -> str:
        texts: list[str] = []
        for page in result or []:
            if not page:
                continue
            for line in page:
                try:
                    text, score = line[1]
                    if float(score) >= 0.30 and str(text).strip():
                        texts.append(str(text).strip())
                except (IndexError, TypeError, ValueError):
                    continue

        return "\n".join(texts).strip()


class PDFOCR:
    """Render PDF pages and OCR only pages whose native text is insufficient."""

    def __init__(
        self,
        *,
        language: str = "en",
        dpi: int = 180,
        min_native_chars: int = 40,
        min_native_words: int = 8,
    ) -> None:
        self.language = language
        self.dpi = dpi
        self.min_native_chars = min_native_chars
        self.min_native_words = min_native_words
        self._engine: PaddleOCRService | None = None

    def extract_pages(self, pdf_bytes: bytes) -> list[tuple[int, str]]:
        pages: list[tuple[int, str]] = []

        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page_number, page in enumerate(doc, start=1):
                native_text = page.get_text("text").strip()

                if self._needs_ocr(native_text):
                    ocr_text = self._ocr_page(page)
                    text = ocr_text if len(self._quality_text(ocr_text)) > len(
                        self._quality_text(native_text)
                    ) else native_text
                else:
                    text = native_text

                if text.strip():
                    pages.append((page_number, text.strip()))

        return pages

    def _needs_ocr(self, text: str) -> bool:
        normalized = self._quality_text(text)
        return (
            len(normalized) < self.min_native_chars
            or len(normalized.split()) < self.min_native_words
        )

    @staticmethod
    def _quality_text(text: str) -> str:
        return " ".join(
            token for token in text.split()
            if any(char.isalnum() for char in token)
        )

    def _ocr_page(self, page: fitz.Page) -> str:
        if self._engine is None:
            self._engine = PaddleOCRService(language=self.language)

        scale = self.dpi / 72.0
        matrix = fitz.Matrix(scale, scale)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        channels = pixmap.n
        image = np.frombuffer(pixmap.samples, dtype=np.uint8)
        image = image.reshape(pixmap.height, pixmap.width, channels)

        return self._engine.extract_text(image)
