from types import SimpleNamespace

from app.services.ai.ocr import PDFOCR


def test_ocr_text_wins_when_native_text_is_only_watermark():
    parser = PDFOCR(min_native_chars=40, min_native_words=8)
    native = "CamScanner"
    ocr = "Object oriented programming uses classes and objects to model entities."
    assert parser._needs_ocr(native) is True
    assert len(parser._quality_text(ocr)) > len(parser._quality_text(native))


def test_ocr_text_does_not_replace_good_native_text():
    parser = PDFOCR(min_native_chars=20, min_native_words=4)
    native = "Abstraction hides implementation details from the user."
    assert parser._needs_ocr(native) is False
