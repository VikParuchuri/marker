import pytest
from marker.schema import BlockTypes


@pytest.mark.skip(reason="This is failing because we need better garbled text detection")
@pytest.mark.filename("water_damage.pdf")
def test_garbled_pdf(pdf_document):
    assert pdf_document.pages[0].structure[0] == '/page/0/Table/0'

    table_block = pdf_document.pages[0].get_block(pdf_document.pages[0].structure[0])
    assert table_block.block_type == BlockTypes.Table
    assert table_block.structure[0] == "/page/0/Line/1"

    table_cell = pdf_document.pages[0].get_block(table_block.structure[0])
    assert table_cell.block_type == BlockTypes.Line
    assert table_cell.structure[0] == "/page/0/Span/2"

    span = pdf_document.pages[0].get_block(table_cell.structure[0])
    assert span.block_type == BlockTypes.Span
    assert "комплекс" in span.text
