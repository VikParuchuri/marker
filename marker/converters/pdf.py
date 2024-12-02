import os
os.environ["TOKENIZERS_PARALLELISM"] = "false" # disables a tokenizers warning

import inspect
from collections import defaultdict
from typing import Any, Dict, List, Type

from marker.builders.document import DocumentBuilder
from marker.builders.layout import LayoutBuilder
from marker.builders.ocr import OcrBuilder
from marker.builders.structure import StructureBuilder
from marker.converters import BaseConverter
from marker.processors.blockquote import BlockquoteProcessor
from marker.processors.code import CodeProcessor
from marker.processors.debug import DebugProcessor
from marker.processors.document_toc import DocumentTOCProcessor
from marker.processors.equation import EquationProcessor
from marker.processors.footnote import FootnoteProcessor
from marker.processors.ignoretext import IgnoreTextProcessor
from marker.processors.line_numbers import LineNumbersProcessor
from marker.processors.list import ListProcessor
from marker.processors.page_header import PageHeaderProcessor
from marker.processors.sectionheader import SectionHeaderProcessor
from marker.processors.table import TableProcessor
from marker.processors.text import TextProcessor
from marker.providers.pdf import PdfProvider
from marker.renderers.markdown import MarkdownRenderer
from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.registry import register_block_class
from marker.util import strings_to_classes


class PdfConverter(BaseConverter):
    """
    A converter for processing and rendering PDF files into Markdown, JSON, HTML and other formats.

    Attributes:
        override_map (Dict[BlockTypes, Type[Block]]): 
            A mapping to override the default block classes for specific block types. 
            The keys are `BlockTypes` enum values, representing the types of blocks, 
            and the values are corresponding `Block` class implementations to use 
            instead of the defaults.
    """
    override_map: Dict[BlockTypes, Type[Block]] = defaultdict()

    def __init__(self, artifact_dict: Dict[str, Any], processor_list: List[str] | None = None, renderer: str | None = None, config=None):
        super().__init__(config)
        
        for block_type, override_block_type in self.override_map.items():
            register_block_class(block_type, override_block_type)

        if processor_list:
            processor_list = strings_to_classes(processor_list)
        else:
            processor_list = [
                BlockquoteProcessor,
                CodeProcessor,
                DocumentTOCProcessor,
                EquationProcessor,
                FootnoteProcessor,
                IgnoreTextProcessor,
                LineNumbersProcessor,
                ListProcessor,
                PageHeaderProcessor,
                SectionHeaderProcessor,
                TableProcessor,
                TextProcessor,
                DebugProcessor,
            ]

        if renderer:
            renderer = strings_to_classes([renderer])[0]
        else:
            renderer = MarkdownRenderer

        self.artifact_dict = artifact_dict
        self.processor_list = processor_list
        self.renderer = renderer

    def resolve_dependencies(self, cls):
        init_signature = inspect.signature(cls.__init__)
        parameters = init_signature.parameters

        resolved_kwargs = {}
        for param_name, param in parameters.items():
            if param_name == 'self':
                continue
            elif param_name == 'config':
                resolved_kwargs[param_name] = self.config
            elif param.name in self.artifact_dict:
                resolved_kwargs[param_name] = self.artifact_dict[param_name]
            elif param.default != inspect.Parameter.empty:
                resolved_kwargs[param_name] = param.default
            else:
                raise ValueError(f"Cannot resolve dependency for parameter: {param_name}")

        return cls(**resolved_kwargs)

    def __call__(self, filepath: str):
        pdf_provider = PdfProvider(filepath, self.config)
        layout_builder = self.resolve_dependencies(LayoutBuilder)
        ocr_builder = self.resolve_dependencies(OcrBuilder)
        document = DocumentBuilder(self.config)(pdf_provider, layout_builder, ocr_builder)
        StructureBuilder(self.config)(document)

        for processor_cls in self.processor_list:
            processor = self.resolve_dependencies(processor_cls)
            processor(document)

        renderer = self.resolve_dependencies(self.renderer)
        return renderer(document)
