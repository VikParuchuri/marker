from marker.v2.providers.pdf import PdfProvider
import tempfile
from typing import Dict, Type

import datasets
import pytest

from marker.v2.builders.document import DocumentBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.builders.ocr import OcrBuilder
from marker.v2.converters.pdf import PdfConverter
from marker.v2.models import setup_detection_model, setup_layout_model, \
    setup_recognition_model, setup_table_rec_model, \
    setup_texify_model
from marker.v2.processors.code import CodeProcessor
from marker.v2.processors.debug import DebugProcessor
from marker.v2.processors.document_toc import DocumentTOCProcessor
from marker.v2.processors.equation import EquationProcessor
from marker.v2.processors.sectionheader import SectionHeaderProcessor
from marker.v2.processors.table import TableProcessor
from marker.v2.processors.text import TextProcessor
from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block
from marker.v2.renderers.markdown import MarkdownRenderer
from marker.v2.renderers.json import JSONRenderer
from marker.v2.schema.registry import register_block_class


@pytest.fixture(scope="session")
def layout_model():
    layout_m = setup_layout_model()
    yield layout_m
    del layout_m


@pytest.fixture(scope="session")
def detection_model():
    detection_m = setup_detection_model()
    yield detection_m
    del detection_m


@pytest.fixture(scope="session")
def texify_model():
    texify_m = setup_texify_model()
    yield texify_m
    del texify_m


@pytest.fixture(scope="session")
def recognition_model():
    ocr_m = setup_recognition_model()
    yield ocr_m
    del ocr_m


@pytest.fixture(scope="session")
def table_rec_model():
    table_rec_m = setup_table_rec_model()
    yield table_rec_m
    del table_rec_m


@pytest.fixture(scope="function")
def config(request):
    config_mark = request.node.get_closest_marker("config")
    config = config_mark.args[0] if config_mark else {}

    override_map: Dict[BlockTypes, Type[Block]] = config.get("override_map", {})
    for block_type, override_block_type in override_map.items():
        register_block_class(block_type, override_block_type)

    return config


@pytest.fixture(scope="function")
def temp_pdf(request):
    filename_mark = request.node.get_closest_marker("filename")
    filename = filename_mark.args[0] if filename_mark else "adversarial.pdf"

    dataset = datasets.load_dataset("datalab-to/pdfs", split="train")
    idx = dataset['filename'].index(filename)

    temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf")
    temp_pdf.write(dataset['pdf'][idx])
    temp_pdf.flush()
    yield temp_pdf


@pytest.fixture(scope="function")
def pdf_provider(request, config, temp_pdf):
    yield PdfProvider(temp_pdf.name, config)


@pytest.fixture(scope="function")
def pdf_document(request, config, pdf_provider, layout_model, recognition_model, detection_model):
    layout_builder = LayoutBuilder(layout_model, config)
    ocr_builder = OcrBuilder(detection_model, recognition_model, config)
    builder = DocumentBuilder(config)
    document = builder(pdf_provider, layout_builder, ocr_builder)
    yield document


@pytest.fixture(scope="function")
def pdf_converter(request, config, layout_model, texify_model, recognition_model, table_rec_model, detection_model, renderer):
    model_dict = {
        "layout_model": layout_model,
        "texify_model": texify_model,
        "recognition_model": recognition_model,
        "table_rec_model": table_rec_model,
        "detection_model": detection_model
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
    yield PdfConverter(
        model_dict=model_dict,
        processor_list=processor_list,
        renderer=renderer,
        config=config
    )


@pytest.fixture(scope="function")
def renderer(request, config):
    if request.node.get_closest_marker("output_format"):
        output_format = request.node.get_closest_marker("output_format").args[0]
        if output_format == "markdown":
            return MarkdownRenderer(config)
        elif output_format == "json":
            return JSONRenderer(config)
        else:
            raise ValueError(f"Unknown output format: {output_format}")
    else:
        return MarkdownRenderer(config)


@pytest.fixture(scope="function")
@pytest.mark.output_format("markdown")
def markdown_output(request, temp_pdf, pdf_converter, renderer):
    yield pdf_converter(temp_pdf.name)
