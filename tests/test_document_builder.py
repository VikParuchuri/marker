from marker.v2.schema.text.line import Line


def test_document_builder(pdf_document):
    first_page = pdf_document.pages[0]
    assert first_page.structure[0] == '/page/0/SectionHeader/0'

    first_block = first_page.get_block(first_page.structure[0])
    assert first_block.block_type == 'SectionHeader'
    assert first_block.text_extraction_method == 'pdftext'

    first_text_block: Line = first_page.get_block(first_block.structure[0])
    assert first_text_block.block_type == 'Line'

    first_span = first_page.get_block(first_text_block.structure[0])
    assert first_span.block_type == 'Span'
    assert first_span.text == 'Subspace Adversarial Training'
    assert first_span.font == 'NimbusRomNo9L-Medi'
    assert first_span.formats == ['plain']

    last_block = first_page.get_block(first_page.structure[-1])
    assert last_block.block_type == 'Text'

    last_text_block: Line = first_page.get_block(last_block.structure[-1])
    assert last_text_block.block_type == 'Line'

    last_span = first_page.get_block(last_text_block.structure[-1])
    assert last_span.block_type == 'Span'
    assert last_span.text == 'prove the quality of single-step AT solutions. However,'
    assert last_span.font == 'NimbusRomNo9L-Regu'
    assert last_span.formats == ['plain']


if __name__ == "__main__":
    from tests.utils import setup_pdf_document

    test_document_builder(setup_pdf_document("adversarial.pdf"))
