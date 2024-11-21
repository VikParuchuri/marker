import pytest

from marker.processors.ignoretext import IgnoreTextProcessor
from marker.schema import BlockTypes


@pytest.mark.filename("bio_pdf.pdf")
@pytest.mark.config({"page_range": list(range(6))})
@pytest.mark.skip(reason="Need to wait for layout model to stabilize before activating.")
def test_ignoretext_processor(pdf_document):
    processor = IgnoreTextProcessor()
    processor(pdf_document)

    page0_header = pdf_document.pages[0].contained_blocks(pdf_document, [BlockTypes.Text])[0]
    assert "bioRxiv" in page0_header.raw_text(pdf_document)
    breakpoint()

    first_span = page0_header.contained_blocks(pdf_document, [BlockTypes.Span])[0]
    assert first_span.ignore_for_output is True
