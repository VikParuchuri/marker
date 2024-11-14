from typing import List

from surya.model.layout.model import load_model
from surya.model.layout.processor import load_processor

from marker.v2.builders.document import DocumentBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.builders.structure import StructureBuilder
from marker.v2.converters import BaseConverter
from marker.v2.providers.pdf import PdfProvider


class PdfConverter(BaseConverter):
    filepath: str
    page_range: List[int] | None = None

    def __call__(self):
        pdf_provider = PdfProvider(self.filepath)

        layout_model = load_model()
        layout_model.processor = load_processor()
        layout_builder = LayoutBuilder(layout_model)

        document = DocumentBuilder()(pdf_provider, layout_builder)
        StructureBuilder()(document)

