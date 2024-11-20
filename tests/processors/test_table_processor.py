import pytest

from tabled.schema import SpanTableCell

from marker.schema import BlockTypes
from marker.processors.table import TableProcessor


@pytest.mark.config({"page_range": [5]})
def test_table_processor(pdf_document, detection_model, recognition_model, table_rec_model):
    processor = TableProcessor(detection_model, recognition_model, table_rec_model)
    processor(pdf_document)

    for block in pdf_document.pages[0].children:
        if block.block_type == BlockTypes.Table:
            assert block.cells is not None
            assert len(block.cells) > 0
            assert isinstance(block.cells[0], SpanTableCell)
