import pytest

from marker.processors.footnote import FootnoteProcessor
from marker.schema import BlockTypes


@pytest.mark.filename("population_stats.pdf")
@pytest.mark.config({"page_range": [4]})
def test_footnote_processor(pdf_document):
    processor = FootnoteProcessor()
    processor(pdf_document)

    page0_footnotes = pdf_document.pages[0].contained_blocks(pdf_document, [BlockTypes.Footnote])
    assert len(page0_footnotes) >= 2

    assert page0_footnotes[-1].raw_text(pdf_document).strip().startswith("5")
