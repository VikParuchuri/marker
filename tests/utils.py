from marker.v2.providers.pdf import PdfProvider
import tempfile

import datasets
from surya.model.layout.model import load_model
from surya.model.layout.processor import load_processor

from marker.v2.builders.document import DocumentBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.schema.document import Document


def setup_pdf_document(filename: str) -> Document:
    dataset = datasets.load_dataset("datalab-to/pdfs", split="train")
    idx = dataset['filename'].index(filename)

    temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf")
    temp_pdf.write(dataset['pdf'][idx])
    temp_pdf.flush()

    layout_model = load_model()
    layout_model.processor = load_processor()

    provider = PdfProvider(temp_pdf.name)
    layout_builder = LayoutBuilder(layout_model)
    builder = DocumentBuilder()
    document = builder(provider, layout_builder)
    return document
