import pytest
from marker.converters.pdf import PdfConverter
from marker.renderers.markdown import MarkdownOutput


@pytest.mark.output_format("markdown")
@pytest.mark.config({"page_range": [0, 1, 2, 3, 7]})
def test_pdf_converter(pdf_converter: PdfConverter, temp_pdf):
    markdown_output: MarkdownOutput = pdf_converter(temp_pdf.name)
    markdown = markdown_output.markdown

    # Basic assertions
    assert len(markdown) > 0
    assert "# Subspace Adversarial Training" in markdown

    # Some assertions for line joining across pages
    assert "AT solutions. However, these methods highly rely on specifically" in markdown  # pgs: 1-2
    assert "(with adversarial perturbations), which harms natural accuracy, " in markdown  # pgs: 3-4

    # Some assertions for line joining across columns
    assert "remain similar across a wide range of choices." in markdown  # pg: 2
    assert "a new scheme for designing more robust and efficient" in markdown  # pg: 8
