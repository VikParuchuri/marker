from typing import List, Optional

from pydantic import BaseModel
from surya.model.layout.model import load_model
from surya.model.layout.processor import load_processor

from marker.v2.builders.document import DocumentBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.builders.structure import StructureBuilder
from marker.v2.converters import BaseConverter
from marker.v2.providers.pdf import PdfProvider


class PdfConverter(BaseConverter):
    def __init__(self, config: Optional[BaseModel] = None):
        super().__init__(config)

        layout_model = load_model()
        layout_model.processor = load_processor()
        self.layout_model = layout_model

    def __call__(self, filepath: str, page_range: List[int] | None = None):
        pdf_provider = PdfProvider(filepath, {"page_range": page_range})

        layout_builder = LayoutBuilder(self.layout_model)
        document = DocumentBuilder()(pdf_provider, layout_builder)
        StructureBuilder()(document)

