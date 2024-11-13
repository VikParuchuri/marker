from marker.v2.builders.structure import StructureBuilder
from tests.utils import setup_pdf_document


def test_structure_builder():
    document = setup_pdf_document('adversarial.pdf')
    structure = StructureBuilder()
    structure(document)
    assert len(document.pages[0].structure) > 0
