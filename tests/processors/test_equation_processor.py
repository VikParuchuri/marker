import pytest

from marker.schema import BlockTypes
from marker.processors.equation import EquationProcessor


@pytest.mark.config({"page_range": [0]})
def test_equation_processor(pdf_document, texify_model):
    processor = EquationProcessor(texify_model)
    processor(pdf_document)

    for block in pdf_document.pages[0].children:
        if block.block_type == BlockTypes.Equation:
            assert block.latex is not None
