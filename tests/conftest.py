from marker.v2.providers.pdf import PdfProvider
import tempfile

import datasets
import pytest
from typing import Dict, Type

from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block
from marker.v2.models import setup_layout_model, setup_texify_model, setup_recognition_model, setup_table_rec_model, \
    setup_detection_model
from marker.v2.builders.document import DocumentBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.builders.ocr import OcrBuilder
from marker.v2.schema.document import Document
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
def pdf_provider(request, config):
    filename_mark = request.node.get_closest_marker("filename")
    filename = filename_mark.args[0] if filename_mark else "adversarial.pdf"

    dataset = datasets.load_dataset("datalab-to/pdfs", split="train")
    idx = dataset['filename'].index(filename)

    temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf")
    temp_pdf.write(dataset['pdf'][idx])
    temp_pdf.flush()
    yield PdfProvider(temp_pdf.name, config)


@pytest.fixture(scope="function")
def pdf_document(request, config, pdf_provider, layout_model, recognition_model, detection_model) -> Document:
    layout_builder = LayoutBuilder(layout_model, config)
    ocr_builder = OcrBuilder(detection_model, recognition_model, config)
    builder = DocumentBuilder(config)
    document = builder(pdf_provider, layout_builder, ocr_builder)
    return document
