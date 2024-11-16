from copy import deepcopy

from marker.v2.schema import BlockTypes
from marker.v2.processors.equation import EquationProcessor


def test_equation_processor(pdf_document, texify_model):
    processor = EquationProcessor(texify_model)

    new_document = deepcopy(pdf_document)
    new_document.pages = [new_document.pages[0]]
    processor(new_document)

    for block in new_document.pages[0].children:
        if block.block_type == BlockTypes.Equation:
            assert block.latex is not None
