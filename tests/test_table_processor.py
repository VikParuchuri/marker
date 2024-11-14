from copy import deepcopy

from tabled.schema import SpanTableCell

from marker.v2.processors.table import TableProcessor


def test_table_processor(pdf_document, detection_model, recognition_model, table_rec_model):
    processor = TableProcessor(detection_model, recognition_model, table_rec_model)

    new_document = deepcopy(pdf_document)
    new_document.pages = [new_document.pages[5]]
    processor(new_document)

    for block in new_document.pages[0].children:
        if block.block_type == "Table":
            assert block.cells is not None
            assert len(block.cells) > 0
            assert isinstance(block.cells[0], SpanTableCell)
