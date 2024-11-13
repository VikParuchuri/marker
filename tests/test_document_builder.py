from marker.v2.providers.pdf import PdfProvider  # this needs to be at the top, long story

import tempfile

import datasets
from surya.model.layout.model import load_model
from surya.model.layout.processor import load_processor

from marker.v2.builders.document import DocumentBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.schema.config.pdf import PdfProviderConfig


def test_document_builder():
    dataset = datasets.load_dataset("datalab-to/pdfs", split="train")
    idx = dataset['filename'].index('adversarial.pdf')

    temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf")
    temp_pdf.write(dataset['pdf'][idx])
    temp_pdf.flush()

    layout_model = load_model()
    layout_model.processor = load_processor()

    provider = PdfProvider(temp_pdf.name, PdfProviderConfig())
    layout_builer = LayoutBuilder(layout_model)
    builder = DocumentBuilder()
    document = builder(provider, layout_builer)
    assert len(document.pages) == len(provider)


if __name__ == "__main__":
    test_document_builder()
