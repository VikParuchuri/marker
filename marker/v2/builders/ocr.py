from typing import Dict, List, Tuple

from surya.ocr import run_ocr

from marker.settings import settings
from marker.v2.builders import BaseBuilder
from marker.v2.providers.pdf import PdfProvider
from marker.v2.schema.document import Document
from marker.v2.schema.polygon import PolygonBox
from marker.v2.schema.registry import get_block_cls
from marker.v2.schema.text.line import Line
from marker.v2.schema.text.span import Span

PageLines = Dict[int, List[Line]]
LineSpans = Dict[int, List[Span]]
PageSpans = Dict[int, LineSpans]


class OcrBuilder(BaseBuilder):
    recognition_batch_size = None
    detection_batch_size = None

    def __init__(self, detection_model, recognition_model, config=None):
        super().__init__(config)

        self.detection_model = detection_model
        self.recognition_model = recognition_model

    def __call__(self, document: Document, provider: PdfProvider):
        page_lines, page_spans = self.ocr_extraction(document, provider)
        self.merge_blocks(document, page_lines, page_spans)

    def get_recognition_batch_size(self):
        if self.recognition_batch_size is not None:
            return self.recognition_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 32
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 32
        return 32

    def get_detection_batch_size(self):
        if self.detection_batch_size is not None:
            return self.detection_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 4
        return 4

    def ocr_extraction(self, document: Document, provider: PdfProvider) -> Tuple[PageLines, PageSpans]:
        page_list = [page for page in document.pages if page.text_extraction_method == "surya"]
        recognition_results = run_ocr(
            images=[page.lowres_image for page in page_list],
            langs=[None] * len(page_list),
            det_model=self.detection_model,
            det_processor=self.detection_model.processor,
            rec_model=self.recognition_model,
            rec_processor=self.recognition_model.processor,
            batch_size=int(self.get_recognition_batch_size()),
            highres_images=[page.highres_image for page in page_list]
        )

        page_lines = {}
        page_spans = {}

        SpanClass = get_block_cls(Span)
        LineClass = get_block_cls(Line)

        for page_id, recognition_result in zip((page.page_id for page in page_list), recognition_results):
            page_spans.setdefault(page_id, {})
            page_lines.setdefault(page_id, [])

            page_size = provider.get_page_bbox(page_id).size
            line_spans = page_spans[page_id]

            for ocr_line_idx, ocr_line in enumerate(recognition_result.text_lines):
                image_polygon = PolygonBox.from_bbox(recognition_result.image_bbox)
                polygon = PolygonBox.from_bbox(ocr_line.bbox).rescale(image_polygon.size, page_size)

                page_lines[page_id].append(LineClass(
                    polygon=polygon,
                    page_id=page_id,
                ))

                line_spans.setdefault(ocr_line_idx, [])
                line_spans[ocr_line_idx].append(SpanClass(
                    text=ocr_line.text,
                    formats=['plain'],
                    page_id=page_id,
                    polygon=polygon,
                    minimum_position=0,
                    maximum_position=0,
                    font='',
                    font_weight=0,
                    font_size=0,
                ))

        return page_lines, page_spans

    def merge_blocks(self, document: Document, page_lines: PageLines, page_spans: PageSpans):
        ocred_pages = [page for page in document.pages if page.text_extraction_method == "surya"]
        for document_page, lines, line_spans in zip(ocred_pages, page_lines.values(), page_spans.values()):
            document_page.merge_blocks(lines, line_spans, text_extraction_method="surya")
