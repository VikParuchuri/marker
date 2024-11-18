import os
import tempfile
from typing import List, Optional

import click
import datasets
from pydantic import BaseModel

from marker.v2.builders.document import DocumentBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.builders.structure import StructureBuilder
from marker.v2.converters import BaseConverter
from marker.v2.processors.equation import EquationProcessor
from marker.v2.processors.table import TableProcessor
from marker.v2.providers.pdf import PdfProvider
from marker.v2.models import setup_layout_model, setup_texify_model, setup_recognition_model, setup_table_rec_model, \
    setup_detection_model
from marker.v2.renderers.markdown import MarkdownRenderer


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
        document = DocumentBuilder()(pdf_provider, layout_builder)
        StructureBuilder()(document)

        equation_processor = EquationProcessor(self.texify_model)
        equation_processor(document)

        table_processor = TableProcessor(self.detection_model, self.recognition_model, self.table_rec_model)
        table_processor(document)

        renderer = MarkdownRenderer()
        return renderer(document)


@click.command()
@click.option("--output", type=click.Path(exists=False), required=False, default="temp")
@click.option("--fname", type=str, default="adversarial.pdf")
def main(output: str, fname: str):
    dataset = datasets.load_dataset("datalab-to/pdfs", split="train")
    idx = dataset['filename'].index(fname)
    out_filename = fname.rsplit(".", 1)[0] + ".md"
    os.makedirs(output, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
        temp_pdf.write(dataset['pdf'][idx])
        temp_pdf.flush()

        converter = PdfConverter()
        rendered = converter(temp_pdf.name)

        with open(os.path.join(output, out_filename), "w+") as f:
            f.write(rendered.markdown)

        for img_name, img in rendered.images.items():
            img.save(os.path.join(output, img_name))


if __name__ == "__main__":
    main()