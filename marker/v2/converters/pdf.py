import json

from marker.settings import settings
from marker.v2.processors.code import CodeProcessor
from marker.v2.processors.document_toc import DocumentTOCProcessor
from marker.v2.providers.pdf import PdfProvider
import os

from marker.v2.renderers.json import JSONRenderer
from marker.v2.util import parse_range_str

os.environ["TOKENIZERS_PARALLELISM"] = "false" # disables a tokenizers warning

from collections import defaultdict
from typing import Dict, Type, List, Any

import click
import inspect

from marker.v2.builders.document import DocumentBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.builders.ocr import OcrBuilder
from marker.v2.builders.structure import StructureBuilder
from marker.v2.converters import BaseConverter
from marker.v2.models import setup_detection_model, setup_layout_model, \
    setup_recognition_model, setup_table_rec_model, setup_texify_model
from marker.v2.processors.equation import EquationProcessor
from marker.v2.processors.sectionheader import SectionHeaderProcessor
from marker.v2.processors.text import TextProcessor
from marker.v2.processors.table import TableProcessor
from marker.v2.renderers.markdown import MarkdownRenderer
from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block
from marker.v2.schema.registry import register_block_class
from marker.v2.processors.debug import DebugProcessor
from marker.v2.processors import BaseProcessor
from marker.v2.renderers import BaseRenderer


class PdfConverter(BaseConverter):
    override_map: Dict[BlockTypes, Type[Block]] = defaultdict()

    def __init__(self, model_dict: Dict[str, Any], processor_list: List[BaseProcessor], renderer: BaseRenderer, config=None):
        super().__init__(config)
        
        for block_type, override_block_type in self.override_map.items():
            register_block_class(block_type, override_block_type)

        self.model_dict = model_dict
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
            elif param.name in self.model_dict:
                resolved_kwargs[param_name] = self.model_dict[param_name]
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

        return self.renderer(document)


@click.command()
@click.argument("fpath", type=str)
@click.option("--output_dir", type=click.Path(exists=False), required=False, default=settings.OUTPUT_DIR)
@click.option("--debug", is_flag=True)
@click.option("--output_format", type=click.Choice(["markdown", "json"]), default="markdown")
@click.option("--pages", type=str, default=None)
@click.option("--force_ocr", is_flag=True)
def main(fpath: str, output_dir: str, debug: bool, output_format: str, pages: str, force_ocr: bool):
    if pages is not None:
        pages = parse_range_str(pages)

    fname_base = os.path.splitext(os.path.basename(fpath))[0]
    output_dir = os.path.join(output_dir, fname_base)
    os.makedirs(output_dir, exist_ok=True)

    config = {
        "page_range": pages,
    }
    if debug:
        config["debug_pdf_images"] = True
        config["debug_layout_images"] = True
        config["debug_json"] = True
        config["debug_data_folder"] = output_dir
    if force_ocr:
        config["force_ocr"] = True

    model_dict = {
        "layout_model": setup_layout_model(),
        "texify_model": setup_texify_model(),
        "recognition_model": setup_recognition_model(),
        "table_rec_model": setup_table_rec_model(),
        "detection_model": setup_detection_model(),
    }
    processor_list = [
        EquationProcessor,
        TableProcessor,
        SectionHeaderProcessor,
        TextProcessor,
        CodeProcessor,
        DocumentTOCProcessor,
        DebugProcessor,
    ]

    if output_format == "markdown":
        renderer = MarkdownRenderer(config)
        fext = "md"
    elif output_format == "json":
        renderer = JSONRenderer(config)
        fext = "json"
    else:
        raise ValueError(f"Unknown output format: {output_format}")

    converter = PdfConverter(
        config=config,
        model_dict=model_dict,
        processor_list=processor_list,
        renderer=renderer
    )
    rendered = converter(fpath)

    with open(os.path.join(output_dir, f"{fname_base}.{fext}"), "w+") as f:
        f.write(rendered.markdown)
    with open(os.path.join(output_dir, f"{fname_base}_meta.json"), "w+") as f:
        f.write(json.dumps(rendered.metadata, indent=2))
    if output_format == "markdown":
        for img_name, img in rendered.images.items():
            img.save(os.path.join(output_dir, img_name), "PNG")

    print(f"Output written to {output_dir}")


if __name__ == "__main__":
    main()
