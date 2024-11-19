from marker.v2.providers.pdf import PdfProvider
import os

from marker.v2.renderers.json import JSONRenderer

os.environ["TOKENIZERS_PARALLELISM"] = "false" # disables a tokenizers warning

import tempfile
from collections import defaultdict
from typing import Dict, Type

import click
import datasets

from marker.v2.builders.document import DocumentBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.builders.ocr import OcrBuilder
from marker.v2.builders.structure import StructureBuilder
from marker.v2.converters import BaseConverter
from marker.v2.models import setup_detection_model, setup_layout_model, \
    setup_recognition_model, setup_table_rec_model, setup_texify_model
from marker.v2.processors.equation import EquationProcessor
from marker.v2.processors.sectionheader import SectionHeaderProcessor
from marker.v2.processors.table import TableProcessor
from marker.v2.renderers.markdown import MarkdownRenderer
from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block
from marker.v2.schema.registry import register_block_class
from marker.v2.processors.debug import DebugProcessor


class PdfConverter(BaseConverter):
    override_map: Dict[BlockTypes, Type[Block]] = defaultdict()

    def __init__(self, config=None, output_format="markdown"):
        super().__init__(config)
        
        for block_type, override_block_type in self.override_map.items():
            register_block_class(block_type, override_block_type)

        self.layout_model = setup_layout_model()
        self.texify_model = setup_texify_model()
        self.recognition_model = setup_recognition_model()
        self.table_rec_model = setup_table_rec_model()
        self.detection_model = setup_detection_model()

        if output_format == "markdown":
            self.renderer = MarkdownRenderer(self.config)
        elif output_format == "json":
            self.renderer = JSONRenderer(self.config)

    def __call__(self, filepath: str):
        pdf_provider = PdfProvider(filepath, self.config)

        layout_builder = LayoutBuilder(self.layout_model, self.config)
        ocr_builder = OcrBuilder(self.detection_model, self.recognition_model, self.config)
        document = DocumentBuilder(self.config)(pdf_provider, layout_builder, ocr_builder)
        StructureBuilder(self.config)(document)

        equation_processor = EquationProcessor(self.texify_model, self.config)
        equation_processor(document)

        table_processor = TableProcessor(self.detection_model, self.recognition_model, self.table_rec_model, self.config)
        table_processor(document)

        section_header_processor = SectionHeaderProcessor(self.config)
        section_header_processor(document)

        debug_processor = DebugProcessor(self.config)
        debug_processor(document)

        return self.renderer(document)


@click.command()
@click.option("--output", type=click.Path(exists=False), required=False, default="temp")
@click.option("--fname", type=str, default="adversarial.pdf")
@click.option("--debug", is_flag=True)
@click.option("--output_format", type=click.Choice(["markdown", "json"]), default="markdown")
def main(output: str, fname: str, debug: bool, output_format: str):
    dataset = datasets.load_dataset("datalab-to/pdfs", split="train")
    idx = dataset['filename'].index(fname)
    fname_base = fname.rsplit(".", 1)[0]
    os.makedirs(output, exist_ok=True)

    config = {}
    if debug:
        config["debug_pdf_images"] = True
        config["debug_layout_images"] = True
        config["debug_json"] = True

    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
        temp_pdf.write(dataset['pdf'][idx])
        temp_pdf.flush()

        converter = PdfConverter(config=config, output_format=output_format)
        rendered = converter(temp_pdf.name)

    if output_format == "markdown":
        out_filename = f"{fname_base}.md"
        with open(os.path.join(output, out_filename), "w+") as f:
            f.write(rendered.markdown)

        for img_name, img in rendered.images.items():
            img.save(os.path.join(output, img_name), "PNG")
    elif output_format == "json":
        out_filename = f"{fname_base}.json"
        with open(os.path.join(output, out_filename), "w+") as f:
            f.write(rendered.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
