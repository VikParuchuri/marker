from surya.schema import LayoutResult

from marker.builders.document import DocumentBuilder
from marker.builders.layout import LayoutBuilder
from marker.builders.ocr import OcrBuilder


def test_blank_page(config, pdf_provider, layout_model, recognition_model, detection_model):
    layout_builder = LayoutBuilder(layout_model, config)
    builder = DocumentBuilder(config)
    document = builder.build_document(pdf_provider)

    layout_results = [LayoutResult(
        bboxes=[],
        image_bbox=p.polygon.bbox,
    ) for p in document.pages]
    page_lines = {p.page_id: [] for p in document.pages}

    layout_builder.add_blocks_to_pages(document.pages, layout_results)
    layout_builder.merge_blocks(document.pages, page_lines)

    assert all([isinstance(p.children, list) for p in document.pages])
    assert all([isinstance(p.structure, list) for p in document.pages])