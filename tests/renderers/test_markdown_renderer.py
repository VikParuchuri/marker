import pytest

from marker.renderers.markdown import MarkdownRenderer
from marker.schema import BlockTypes
from marker.schema.blocks import TableCell


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

@pytest.mark.config({"page_range": [5]})
def test_markdown_renderer_tables(pdf_document):
    table = pdf_document.contained_blocks((BlockTypes.Table,))[0]
    page = pdf_document.pages[0]

    cell = TableCell(
        polygon=table.polygon,
        text_lines=["54<i>.45</i>67<br>89<math>x</math>"],
        rowspan=1,
        colspan=1,
        row_id=0,
        col_id=0,
        is_header=False,
        page_id=page.page_id,
    )
    page.add_full_block(cell)
    table.structure = []
    table.add_structure(cell)

    renderer = MarkdownRenderer()
    md = renderer(pdf_document).markdown
    assert "54 <i>.45</i> 67<br>89 $x$" in md


