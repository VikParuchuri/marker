import pytest

from marker.builders.document import DocumentBuilder
from marker.builders.layout import LayoutBuilder
from marker.schema import BlockTypes

@pytest.mark.config({"page_range": [0], "strip_existing_ocr": True})
@pytest.mark.filename("handwritten.pdf")
def test_strip_ocr(pdf_provider):
    # Ensure that the OCR text isn't extracted
    assert len(pdf_provider.page_lines) == 0

@pytest.mark.config({"page_range": [0]})
@pytest.mark.filename("handwritten.pdf")
def test_keep_ocr(pdf_provider):
    assert len(pdf_provider.page_lines) == 1