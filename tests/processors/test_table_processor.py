import pytest
from marker.renderers.json import JSONRenderer

from marker.renderers.markdown import MarkdownRenderer
from marker.schema import BlockTypes
from marker.processors.table import TableProcessor
from marker.schema.blocks import TableCell


@pytest.mark.config({"page_range": [5]})
def test_table_processor(pdf_document, detection_model, recognition_model, table_rec_model):
    processor = TableProcessor(detection_model, recognition_model, table_rec_model)
    processor(pdf_document)

    for block in pdf_document.pages[0].children:
        if block.block_type == BlockTypes.Table:
            children = block.contained_blocks(pdf_document, (BlockTypes.TableCell,))
            assert children
            assert len(children) > 0
            assert isinstance(children[0], TableCell)

    assert len(pdf_document.contained_blocks((BlockTypes.Table,))) == 2

    renderer = MarkdownRenderer()
    table_output = renderer(pdf_document)
    assert "Schedule" in table_output.markdown


@pytest.mark.filename("table_ex.pdf")
@pytest.mark.config({"page_range": [0], "force_ocr": True})
def test_avoid_double_ocr(pdf_document, detection_model, recognition_model, table_rec_model):
    tables = pdf_document.contained_blocks((BlockTypes.Table,))
    lines = tables[0].contained_blocks(pdf_document, (BlockTypes.Line,))
    assert len(lines) == 0

    processor = TableProcessor(detection_model, recognition_model, table_rec_model, config={"force_ocr": True})
    processor(pdf_document)

    renderer = MarkdownRenderer()
    table_output = renderer(pdf_document)
    assert "Participants" in table_output.markdown

