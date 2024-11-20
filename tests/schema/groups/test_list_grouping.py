import pytest

from marker.builders.structure import StructureBuilder
from marker.schema import BlockTypes


@pytest.mark.config({"page_range": [4]})
def test_list_grouping(pdf_document):
    structure = StructureBuilder()
    structure(pdf_document)

    page = pdf_document.pages[0]
    list_groups = []
    for block in page.children:
        if block.block_type == BlockTypes.ListGroup:
            list_groups.append(block)

    assert len(list_groups) == 1
