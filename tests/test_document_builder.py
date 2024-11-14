from marker.v2.providers.pdf import PdfProvider  # this needs to be at the top, long story

import tempfile

import datasets

from marker.v2.builders.document import DocumentBuilder
from marker.v2.builders.layout import LayoutBuilder


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


if __name__ == "__main__":
    test_document_builder()
