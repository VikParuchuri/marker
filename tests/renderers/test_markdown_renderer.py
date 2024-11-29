import pytest

from marker.renderers.markdown import MarkdownRenderer


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


@pytest.mark.config({"page_range": [0, 1]})
def test_markdown_renderer_metadata(pdf_document):
    renderer = MarkdownRenderer({"paginate_output": True})
    metadata = renderer(pdf_document).metadata
    assert "table_of_contents" in metadata


@pytest.mark.config({"page_range": [0, 1]})
def test_markdown_renderer_images(pdf_document):
    renderer = MarkdownRenderer({"extract_images": False})
    markdown_output = renderer(pdf_document)
    
    assert len(markdown_output.images) == 0
    assert '![](' not in markdown_output.markdown
