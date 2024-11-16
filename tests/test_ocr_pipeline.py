from marker.v2.schema import BlockTypes
from marker.v2.schema.text.line import Line
from tests.utils import setup_pdf_document


def test_ocr_pipeline():
    pdf_document = setup_pdf_document(
        "adversarial.pdf",
        document_builder_config={
            "force_ocr": True
        }
    )

    first_page = pdf_document.pages[0]
    assert first_page.structure[0] == '/page/0/SectionHeader/0'

    first_block = first_page.get_block(first_page.structure[0])
    assert first_block.text_extraction_method == 'surya'
    assert first_block.block_type == BlockTypes.SectionHeader

    first_text_block: Line = first_page.get_block(first_block.structure[0])
    assert first_text_block.block_type == BlockTypes.Line

    first_span = first_page.get_block(first_text_block.structure[0])
    assert first_span.block_type == BlockTypes.Span
    assert first_span.text.strip() == 'Subspace Adversarial Training'


if __name__ == "__main__":
    test_ocr_pipeline()
