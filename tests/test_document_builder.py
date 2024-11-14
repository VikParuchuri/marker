from marker.v2.providers.pdf import PdfProvider  # this needs to be at the top, long story

import tempfile

import datasets

from marker.v2.builders.document import DocumentBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.schema.text.line import Line


def test_document_builder(layout_model):
    dataset = datasets.load_dataset("datalab-to/pdfs", split="train")
    idx = dataset['filename'].index('adversarial.pdf')

    temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf")
    temp_pdf.write(dataset['pdf'][idx])
    temp_pdf.flush()

    provider = PdfProvider(temp_pdf.name)
    layout_builer = LayoutBuilder(layout_model)
    builder = DocumentBuilder()

    document = builder(provider, layout_builer)
    assert len(document.pages) == len(provider)

    first_page = document.pages[0]
    assert first_page.structure[0] == '/page/0/Section-header/0'

    first_block = first_page.get_block(first_page.structure[0])
    assert first_block.block_type == 'Section-header'
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
    from surya.model.layout.model import load_model
    from surya.model.layout.processor import load_processor

    layout_model = load_model()
    layout_model.processor = load_processor()

    test_document_builder(layout_model)
