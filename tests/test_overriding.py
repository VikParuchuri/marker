import pytest

from marker.v2.schema import BlockTypes
from marker.v2.schema.document import Document
from marker.v2.schema.blocks import SectionHeader


class NewSectionHeader(SectionHeader):
    pass


@pytest.mark.config({
    "page_range": [0],
    "override_map": {BlockTypes.SectionHeader: NewSectionHeader}
})
def test_overriding(pdf_document: Document):
    assert pdf_document.pages[0]\
        .get_block(pdf_document.pages[0].structure[0]).__class__ == NewSectionHeader
