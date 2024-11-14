from marker.v2.processors.equation import EquationProcessor


def test_equation_processor(pdf_document, texify_model):
    processor = EquationProcessor(texify_model)

    pdf_document.pages = [pdf_document.pages[0]]
    processor(pdf_document)

    for block in pdf_document.pages[0].children:
        if block.block_type == "Equation":
            assert block.latex is not None
