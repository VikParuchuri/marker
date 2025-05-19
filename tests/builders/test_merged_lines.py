import pytest

from marker.schema import BlockTypes


@pytest.mark.config({"page_range": [6], "format_lines": True, "disable_ocr": True})
@pytest.mark.filename("bad_math.pdf")
def test_keep_ocr(pdf_document):
    contained_lines = pdf_document.pages[0].contained_blocks(
        pdf_document, [BlockTypes.Line]
    )

    # Check that we grabbed the right text
    assert "Lemma" in contained_lines[-1].formatted_text(pdf_document)
    assert "distribution" in contained_lines[-2].formatted_text(pdf_document)

    # Line 2 comes after line 1
    assert contained_lines[-1].polygon.bbox[1] > contained_lines[-2].polygon.bbox[3]
