from typing import Tuple

from marker.builders.document import DocumentBuilder
from marker.builders.line import LineBuilder
from marker.builders.ocr import OcrBuilder
from marker.converters.pdf import PdfConverter
from marker.processors import BaseProcessor
from marker.processors.equation import get_equation_processor
from marker.providers.registry import provider_from_filepath
from marker.renderers.ocr_json import OCRJSONRenderer
from marker.providers.mathpix import MathpixProvider
from marker.settings import settings


class OCRConverter(PdfConverter):
    default_processors: Tuple[BaseProcessor, ...] = (get_equation_processor(),)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.config:
            self.config = {}

        self.config["format_lines"] = True
        self.renderer = OCRJSONRenderer
        
        # Initialize Mathpix provider
        self.mathpix_provider = MathpixProvider(
            app_id=settings.MATHPIX_APP_ID,
            app_key=settings.MATHPIX_APP_KEY
        )

    def build_document(self, filepath: str):
        provider_cls = provider_from_filepath(filepath)
        layout_builder = self.resolve_dependencies(self.layout_builder_class)
        line_builder = self.resolve_dependencies(LineBuilder)
        ocr_builder = self.resolve_dependencies(OcrBuilder)
        document_builder = DocumentBuilder(self.config)

        provider = provider_cls(filepath, self.config)
        document = document_builder(provider, layout_builder, line_builder, ocr_builder)

        # Initialize processors
        for processor in self.processor_list:
            processor(document)

        return document

    def __call__(self, filepath: str):
        document = self.build_document(filepath)
        renderer = self.resolve_dependencies(self.renderer)
        return renderer(document)
