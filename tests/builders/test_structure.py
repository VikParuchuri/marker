import pytest

from marker.builders.structure import StructureBuilder


@pytest.mark.config({"page_range": [0]})
def test_structure_builder(pdf_document):
    structure = StructureBuilder()
    structure(pdf_document)
    assert len(pdf_document.pages[0].structure) > 0
