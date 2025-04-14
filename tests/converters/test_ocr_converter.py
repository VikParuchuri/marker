import pytest

from marker.converters.ocr import OCRConverter
from marker.renderers.ocr_json import OCRJSONOutput


def _ocr_converter(config, model_dict, temp_pdf):
    converter = OCRConverter(artifact_dict=model_dict, config=config)

    ocr_json: OCRJSONOutput = converter(temp_pdf.name)
    pages = ocr_json.pages

    assert len(pages) == 1
    breakpoint()


@pytest.mark.config({"page_range": [0]})
def test_ocr_converter(config, model_dict, temp_doc):
    _ocr_converter(config, model_dict, temp_doc)
