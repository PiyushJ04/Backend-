from types import SimpleNamespace

from app.services.ai.ocr import PaddleOCRService, PDFOCR


def test_ocr_v3_result_extracts_text_and_filters_low_confidence():
    item = SimpleNamespace(
        json={
            "res": {
                "rec_texts": ["Abstraction", "noise"],
                "rec_scores": [0.98, 0.10],
            }
        }
    )
    assert PaddleOCRService._extract_v3_result([item]) == "Abstraction"


def test_ocr_legacy_result_extracts_text_and_filters_low_confidence():
    result = [[
        [[], ("Encapsulation", 0.95)],
        [[], ("noise", 0.10)],
    ]]
    assert PaddleOCRService._extract_legacy_result(result) == "Encapsulation"


def test_short_native_text_triggers_ocr():
    parser = PDFOCR(min_native_chars=40, min_native_words=8)
    assert parser._needs_ocr("CamScanner") is True


def test_sufficient_native_text_skips_ocr():
    parser = PDFOCR(min_native_chars=20, min_native_words=4)
    text = "Abstraction hides implementation details from the user."
    assert parser._needs_ocr(text) is False
