import pytest

from marker.renderers.markdown import MarkdownRenderer


@pytest.mark.config({"page_range": [0]})
@pytest.mark.filename("A17_FlightPlan.pdf")
def test_disable_extract_images(pdf_document):
    renderer = MarkdownRenderer({"extract_images": False})
    md = renderer(pdf_document).markdown

    # Verify markdown
    assert len(md) == 0


@pytest.mark.config({"page_range": [0]})
@pytest.mark.filename("A17_FlightPlan.pdf")
def test_extract_images(pdf_document):
    renderer = MarkdownRenderer()
    md = renderer(pdf_document).markdown

    # Verify markdown
    assert "jpeg" in md