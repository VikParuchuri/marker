from PIL import Image

from marker.builders.ocr import OcrBuilder


def test_blank_char_builder(recognition_model):
    builder = OcrBuilder(recognition_model)
    image = Image.new("RGB", (100, 100))
    spans = builder.spans_from_html_chars([], None, image)  # Test with empty char list
    assert len(spans) == 0
