import pytest

from marker.processors.line_merge import LineMergeProcessor
from marker.schema import BlockTypes

@pytest.mark.config({"page_range": [1]})
def test_inline_box_nomerging(pdf_document, config):
    first_page = pdf_document.pages[0]
    block = pdf_document.get_block(first_page.structure[1]) # First inline math block
    line_count = len(block.contained_blocks(pdf_document, (BlockTypes.Line,)))
    assert line_count == 46

    merger = LineMergeProcessor(config)
    merger(pdf_document)

    line_count = len(block.contained_blocks(pdf_document, (BlockTypes.Line,)))
    assert line_count == 46


@pytest.mark.config({"page_range": [1], "use_llm": True})
def test_inline_box_merging(pdf_document, config):
    first_page = pdf_document.pages[0]
    block = pdf_document.get_block(first_page.structure[1]) # First inline math block
    line_count = len(block.contained_blocks(pdf_document, (BlockTypes.Line,)))
    assert line_count == 21

    merger = LineMergeProcessor(config)
    merger(pdf_document)

    line_count = len(block.contained_blocks(pdf_document, (BlockTypes.Line,)))
    assert line_count == 21