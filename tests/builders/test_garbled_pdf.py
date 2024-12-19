import pytest

from marker.builders.document import DocumentBuilder
from marker.builders.layout import LayoutBuilder
from marker.schema import BlockTypes

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


@pytest.mark.filename("hindi_judgement.pdf")
@pytest.mark.config({"page_range": [2, 3]})
def test_garbled_builder(config, pdf_provider, layout_model, ocr_error_model):
    layout_builder = LayoutBuilder(layout_model, ocr_error_model, config)
    builder = DocumentBuilder(config)
    document = builder.build_document(pdf_provider)

    bad_ocr_results = layout_builder.surya_ocr_error_detection(document.pages, pdf_provider.page_lines)
    assert len(bad_ocr_results.labels) == 2
    assert all([l == "bad" for l in bad_ocr_results.labels])


@pytest.mark.filename("adversarial.pdf")
@pytest.mark.config({"page_range": [2, 3]})
def test_nongarbled_builder(config, pdf_provider, layout_model, ocr_error_model):
    layout_builder = LayoutBuilder(layout_model, ocr_error_model, config)
    builder = DocumentBuilder(config)
    document = builder.build_document(pdf_provider)

    bad_ocr_results = layout_builder.surya_ocr_error_detection(document.pages, pdf_provider.page_lines)
    assert len(bad_ocr_results.labels) == 2
    assert all([l == "good" for l in bad_ocr_results.labels])


