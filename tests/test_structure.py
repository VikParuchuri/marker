from marker.v2.builders.structure import StructureBuilder
from tests.utils import setup_pdf_document


def test_structure_builder(pdf_document):
    structure = StructureBuilder()
    structure(pdf_document)
    assert len(pdf_document.pages[0].structure) > 0
