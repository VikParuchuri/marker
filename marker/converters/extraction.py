import json
import re

from marker.builders.document import DocumentBuilder
from marker.builders.line import LineBuilder
from marker.builders.ocr import OcrBuilder
from marker.builders.structure import StructureBuilder
from marker.converters.pdf import PdfConverter
from marker.extractors.page import PageExtractor
from marker.providers.registry import provider_from_filepath

from marker.renderers.extraction import ExtractionOutput
from marker.renderers.markdown import MarkdownRenderer


class ExtractionConverter(PdfConverter):
    pattern: str = r"{\d+\}-{48}\n\n"

    def build_document(self, filepath: str):
        provider_cls = provider_from_filepath(filepath)
        layout_builder = self.resolve_dependencies(self.layout_builder_class)
        line_builder = self.resolve_dependencies(LineBuilder)
        ocr_builder = self.resolve_dependencies(OcrBuilder)
        provider = provider_cls(filepath, self.config)
        document = DocumentBuilder(self.config)(
            provider, layout_builder, line_builder, ocr_builder
        )
        structure_builder_cls = self.resolve_dependencies(StructureBuilder)
        structure_builder_cls(document)

        for processor in self.processor_list:
            processor(document)

        return document, provider

    def __call__(self, filepath: str):
        self.config["paginate_output"] = True  # Ensure we can split the output properly
        self.config["output_format"] = (
            "markdown"  # Output must be markdown for extraction
        )
        document, provider = self.build_document(filepath)
        renderer = self.resolve_dependencies(MarkdownRenderer)
        output = renderer(document)

        output_pages = re.split(self.pattern, output.markdown)[
            1:
        ]  # Split output into pages

        extractor = self.resolve_dependencies(PageExtractor)

        all_json = []
        for page, page_md in zip(document.pages, output_pages):
            extracted_model = extractor(document, page, page_md.strip())
            extracted_json = extracted_model.model_dump_json()
            print(extracted_json)
            all_json.append(extracted_json)
        return ExtractionOutput(json=json.dumps(all_json, indent=4, ensure_ascii=False))
