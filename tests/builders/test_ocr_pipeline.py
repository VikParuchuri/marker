import pytest

from marker.schema import BlockTypes
from marker.schema.text.line import Line


@pytest.mark.config({"force_ocr": True, "page_range": [0]})
def test_ocr_pipeline(pdf_document):
    first_page = pdf_document.pages[0]
    assert first_page.structure[0] == '/page/0/SectionHeader/0'

    first_block = first_page.get_block(first_page.structure[0])
    assert first_block.text_extraction_method == 'surya'
    assert first_block.block_type == BlockTypes.SectionHeader

    first_text_block: Line = first_page.get_block(first_block.structure[0])
    assert first_text_block.block_type == BlockTypes.Line

    first_span = first_page.get_block(first_text_block.structure[0])
    assert first_span.block_type == BlockTypes.Span
    assert first_span.text.strip() == 'Subspace Adversarial Training'

    # Ensure we match all text lines up properly
    # Makes sure the OCR bbox is being scaled to the same scale as the layout boxes
    text_lines = first_page.contained_blocks(pdf_document, (BlockTypes.Line,))
    text_blocks = first_page.contained_blocks(pdf_document, (BlockTypes.Text,))
    assert len(text_lines) == 75

    # Ensure the bbox sizes match up
    max_line_position = max([line.polygon.y_end for line in text_lines])
    max_block_position = max([block.polygon.y_end for block in text_blocks if block.source == "layout"])
    assert max_line_position <= (max_block_position * 1.02)

