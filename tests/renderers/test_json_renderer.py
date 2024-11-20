import pytest

from marker.renderers.json import JSONRenderer


@pytest.mark.config({"page_range": [0]})
def test_markdown_renderer_pagination(pdf_document):
    renderer = JSONRenderer()
    pages = renderer(pdf_document).children

    assert len(pages) == 1
    assert pages[0].block_type == "Page"
    assert pages[0].children[0].block_type == "SectionHeader"