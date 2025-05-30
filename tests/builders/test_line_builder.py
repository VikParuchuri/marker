import pytest

from marker.schema import BlockTypes

# Page contains provider lines that are longer than detected lines
# Any bad merging will cause broken final OCR results with format lines
@pytest.mark.filename("mixed_eng_hindi.pdf")
@pytest.mark.config({"page_range": [2], "format_lines": True})
def test_provider_detected_line_merge(pdf_document):
    page = pdf_document.pages[0]
    text_lines = page.contained_blocks(pdf_document, (BlockTypes.Line,))

    # This count includes detected lines merged in with provider lines
    assert len(text_lines) == 83

# Page provider lines only contain english, while the hindi is missing
# format_lines should fill in the missing lines
@pytest.mark.filename("mixed_eng_hindi.pdf")
@pytest.mark.config({"page_range": [0], "format_lines": True})
def test_fill_missing_provider_lines(pdf_document):
    page = pdf_document.pages[0]
    raw_text = page.raw_text(pdf_document)
    assert "प्राधिकार से प्रकाशित" in raw_text
    assert "खान मंत्रालय" in raw_text