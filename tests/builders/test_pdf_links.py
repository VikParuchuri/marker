import pytest

from marker.converters.pdf import PdfConverter
from marker.renderers.markdown import MarkdownOutput
from marker.schema import BlockTypes
from marker.schema.document import Document


@pytest.mark.filename("arxiv_test.pdf")
@pytest.mark.output_format("markdown")
@pytest.mark.config({"page_range": [1]})
def test_pdf_links(pdf_document: Document, pdf_converter: PdfConverter, temp_pdf):
    first_page = pdf_document.pages[0]

    for section_header_span in first_page.contained_blocks(pdf_document, (BlockTypes.Span,)):
        if section_header_span.text == " II.":
            assert section_header_span.url == "#page-1-0"
            break
    else:
        raise ValueError("Could not find II. in the first page")

    section_header_block = first_page.contained_blocks(pdf_document, (BlockTypes.SectionHeader,))[0]
    assert section_header_block.raw_text(pdf_document) == 'II. THEORETICAL FRAMEWORK\n'

    section_header_span = section_header_block.contained_blocks(pdf_document, (BlockTypes.Span,))[0]
    assert section_header_span.anchors == ['page-1-0']

    markdown_output: MarkdownOutput = pdf_converter(temp_pdf.name)
    markdown = markdown_output.markdown

    assert '[II.](#page-1-0)' in markdown
    assert '<span id="page-1-0"/>II. THEORETICAL FRAMEWORK' in markdown
