import tempfile

import datasets
import pytest
from surya.model.layout.model import load_model
from surya.model.layout.processor import load_processor

from marker.v2.builders.document import DocumentBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.providers.pdf import PdfProvider
from marker.v2.schema.document import Document


@pytest.fixture(scope="session")
def layout_model():
    layout_model = load_model()
    layout_model.processor = load_processor()
    yield layout_model
    del layout_model


@pytest.fixture(scope="session")
def pdf_document(request, layout_model) -> Document:
    marker = request.node.get_closest_marker("filename")
    if marker is None:
        filename = "adversarial.pdf"
    else:
        filename = marker.args[0]
    dataset = datasets.load_dataset("datalab-to/pdfs", split="train")
    idx = dataset['filename'].index(filename)

    temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf")
    temp_pdf.write(dataset['pdf'][idx])
    temp_pdf.flush()

    provider = PdfProvider(temp_pdf.name)
    layout_builder = LayoutBuilder(layout_model)
    builder = DocumentBuilder()
    document = builder(provider, layout_builder)
    return document