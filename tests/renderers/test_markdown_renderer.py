import pytest

from marker.v2.renderers.markdown import MarkdownRenderer


@pytest.mark.config({"page_range": [0]})
def test_markdown_renderer(pdf_document):
    renderer = MarkdownRenderer()
    md = renderer(pdf_document).markdown

    # Verify markdown
    assert '# Subspace Adversarial Training' in md


@pytest.mark.config({"page_range": [0, 1], "paginate_output": True})
def test_markdown_renderer_pagination(pdf_document):
    renderer = MarkdownRenderer({"paginate_output": True})
    md = renderer(pdf_document).markdown

    assert "{0}-" in md
    assert "{1}-" in md