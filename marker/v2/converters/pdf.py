from marker.v2.providers.pdf import PdfProvider

import tempfile
from typing import List, Optional

import datasets
from pydantic import BaseModel

from marker.v2.builders.document import DocumentBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.builders.ocr import OcrBuilder
from marker.v2.builders.structure import StructureBuilder
from marker.v2.converters import BaseConverter
from marker.v2.processors.equation import EquationProcessor
from marker.v2.processors.table import TableProcessor
from marker.v2.models import setup_layout_model, setup_texify_model, setup_recognition_model, setup_table_rec_model, \
    setup_detection_model
from marker.v2.renderers.line import LineRenderer
from marker.v2.renderers.span import SpanRenderer


class PdfConverter(BaseConverter):
    def __init__(self, config: Optional[BaseModel] = None):
        super().__init__(config)

        self.layout_model = setup_layout_model()
        self.texify_model = setup_texify_model()
        self.recognition_model = setup_recognition_model()
        self.table_rec_model = setup_table_rec_model()
        self.detection_model = setup_detection_model()

    def __call__(self, filepath: str, page_range: List[int] | None = None):
        pdf_provider = PdfProvider(filepath, {"page_range": page_range})

        layout_builder = LayoutBuilder(self.layout_model)
        ocr_builder = OcrBuilder(self.recognition_model)
        document = DocumentBuilder()(pdf_provider, layout_builder, ocr_builder)
        StructureBuilder()(document)

        equation_processor = EquationProcessor(self.texify_model)
        equation_processor(document)

        # TODO: re-enable once we add OCR method
        # table_processor = TableProcessor(self.detection_model, self.recognition_model, self.table_rec_model)
        # table_processor(document)

        renderer_lst = [SpanRenderer(), LineRenderer()]
        rendered = document.render(renderer_lst)
        return rendered


if __name__ == "__main__":
    dataset = datasets.load_dataset("datalab-to/pdfs", split="train")
    idx = dataset['filename'].index('adversarial.pdf')

    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
        temp_pdf.write(dataset['pdf'][idx])
        temp_pdf.flush()

        converter = PdfConverter()
        rendered = converter(temp_pdf.name)

        print(rendered)
