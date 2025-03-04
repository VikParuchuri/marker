import pytest

from marker.builders.document import DocumentBuilder
from marker.builders.line import LineBuilder
from marker.processors.table import TableProcessor
from marker.schema import BlockTypes

@pytest.mark.filename("water_damage.pdf")
def test_garbled_pdf(pdf_document, detection_model, recognition_model, table_rec_model):
    assert pdf_document.pages[0].structure[0] == '/page/0/Table/0'

    table_block = pdf_document.pages[0].get_block(pdf_document.pages[0].structure[0])
    assert table_block.block_type == BlockTypes.Table
    assert table_block.structure[0] == "/page/0/Line/1"

    table_cell = pdf_document.pages[0].get_block(table_block.structure[0])
    assert table_cell.block_type == BlockTypes.Line
    assert table_cell.structure[0] == "/page/0/Span/3"

    # We don't OCR in the initial pass, only with the TableProcessor
    processor = TableProcessor(detection_model, recognition_model, table_rec_model)
    processor(pdf_document)

    table = pdf_document.pages[0].contained_blocks(pdf_document, (BlockTypes.Table,))[0]
    assert "варіант" in table.raw_text(pdf_document)

    table_cell = pdf_document.pages[0].get_block(table_block.structure[0])
    assert table_cell.block_type == BlockTypes.TableCell


@pytest.mark.filename("hindi_judgement.pdf")
@pytest.mark.config({"page_range": [2, 3], "disable_ocr": True})
def test_garbled_builder(config, doc_provider, detection_model, inline_detection_model, ocr_error_model):
    line_builder = LineBuilder(detection_model, inline_detection_model, ocr_error_model, config)
    builder = DocumentBuilder(config)
    document = builder.build_document(doc_provider)

    bad_ocr_results = line_builder.ocr_error_detection(document.pages, doc_provider.page_lines)
    assert len(bad_ocr_results.labels) == 2
    assert any([l == "bad" for l in bad_ocr_results.labels])


@pytest.mark.filename("adversarial.pdf")
@pytest.mark.config({"page_range": [2, 3], "disable_ocr": True})
def test_nongarbled_builder(config, doc_provider, detection_model, inline_detection_model, ocr_error_model):
    line_builder = LineBuilder(detection_model, inline_detection_model, ocr_error_model, config)
    builder = DocumentBuilder(config)
    document = builder.build_document(doc_provider)

    bad_ocr_results = line_builder.ocr_error_detection(document.pages, doc_provider.page_lines)
    assert len(bad_ocr_results.labels) == 2
    assert all([l == "good" for l in bad_ocr_results.labels])


