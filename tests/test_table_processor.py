from tabled.schema import SpanTableCell

from marker.v2.processors.table import TableProcessor


def test_table_processor(pdf_document, detection_model, recognition_model, table_rec_model):
    processor = TableProcessor(detection_model, recognition_model, table_rec_model)

    pdf_document.pages = [pdf_document.pages[5]]
    processor(pdf_document)

    for block in pdf_document.pages[0].children:
        if block.block_type == "Table":
            assert block.cells is not None
            assert len(block.cells) > 0
            assert isinstance(block.cells[0], SpanTableCell)
