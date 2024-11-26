from marker.providers.pdf import PdfProvider
import tempfile

import datasets
from marker.models import setup_layout_model, setup_recognition_model, setup_detection_model
from marker.builders.document import DocumentBuilder
from marker.builders.layout import LayoutBuilder
from marker.builders.ocr import OcrBuilder
from marker.schema.document import Document


def setup_pdf_provider(
    filename='adversarial.pdf',
    config=None,
) -> PdfProvider:
    dataset = datasets.load_dataset("datalab-to/pdfs", split="train")
    idx = dataset['filename'].index(filename)

    temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf")
    temp_pdf.write(dataset['pdf'][idx])
    temp_pdf.flush()

    provider = PdfProvider(temp_pdf.name, config)
    return provider
