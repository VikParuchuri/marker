import json
import re

from marker.builders.document import DocumentBuilder
from marker.builders.line import LineBuilder
from marker.builders.ocr import OcrBuilder
from marker.builders.structure import StructureBuilder
from marker.converters.pdf import PdfConverter
from marker.extractors.page import PageExtractor, json_schema_to_base_model
from marker.providers.registry import provider_from_filepath

from marker.renderers.extraction import ExtractionRenderer, ExtractionOutput
from marker.renderers.markdown import MarkdownRenderer

from marker.logger import get_logger

logger = get_logger()


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

    def __call__(self, filepath: str) -> ExtractionOutput:
        self.config["paginate_output"] = True  # Ensure we can split the output properly
        self.config["output_format"] = (
            "markdown"  # Output must be markdown for extraction
        )
        try:
            json_schema_to_base_model(json.loads(self.config["page_schema"]))
        except Exception as e:
            logger.error(f"Could not parse page schema: {e}")
            raise ValueError(
                "Could not parse your page schema. Please check the schema format."
            )

        document, provider = self.build_document(filepath)
        renderer = self.resolve_dependencies(MarkdownRenderer)
        output = renderer(document)

        output_pages = re.split(self.pattern, output.markdown)[
            1:
        ]  # Split output into pages

        # This needs an LLM service for extraction, this sets it in the extractor
        if not self.artifact_dict["llm_service"]:
            self.artifact_dict["llm_service"] = self.resolve_dependencies(
                self.default_llm_service
            )

        extractor = self.resolve_dependencies(PageExtractor)
        renderer = self.resolve_dependencies(ExtractionRenderer)

        pnums = provider.page_range
        all_json = {}
        for page, page_md, pnum in zip(document.pages, output_pages, pnums):
            extracted_json = extractor(document, page, page_md.strip())
            all_json[pnum] = extracted_json

        merged = renderer(all_json)
        return merged
