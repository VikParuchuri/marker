from typing import Dict, List

from surya.detection import batch_text_detection
from surya.ocr import run_recognition

from marker.settings import settings
from marker.v2.builders import BaseBuilder
from marker.v2.providers.pdf import PdfProvider
from marker.v2.schema.blocks import Block
from marker.v2.schema.document import Document
from marker.v2.schema.polygon import PolygonBox
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
        detected_page_lines = self.text_detection(document, provider)
        detected_line_spans = self.ocr_extraction(detected_page_lines, document, provider)
        self.merge_blocks(document, detected_page_lines, detected_line_spans)

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

    def text_detection(self, document: Document, provider: PdfProvider) -> PageLines:
        page_lines: PageLines = {}
        page_list = [page for page in document.pages if page.text_extraction_method == "surya"]

        page_detection_results = batch_text_detection(
            [page.lowres_image for page in page_list],
            self.detection_model,
            self.detection_model.processor,
            batch_size=int(self.get_detection_batch_size())
        )

        page_ids = [page.page_id for page in page_list]
        for page_id, page_detection_result in zip(page_ids, page_detection_results):
            image_size = PolygonBox.from_bbox(page_detection_result.image_bbox).size
            page_size = provider.get_page_bbox(page_id).size
            lines: List[Line] = []
            for line in page_detection_result.bboxes:
                polygon = PolygonBox(polygon=line.polygon).rescale(image_size, page_size)
                lines.append(Line(polygon=polygon, page_id=page_id))
            page_lines[page_id] = lines
        return page_lines

    def ocr_extraction(self, page_lines: PageLines, document: Document, provider: PdfProvider):
        page_id_list: List[int] = []
        ocr_bbox_page_list: List[List[List[int]]] = []
        ocr_page_line_idx_list: List[List[int]] = []

        for page_id, lines in page_lines.items():
            page_size = provider.get_page_bbox(page_id).size
            image_size = document.pages[page_id].highres_image.size
            ocr_bbox_list = []
            ocr_line_idx_list = []
            for line_idx, line in enumerate(lines):
                ocr_polygon = line.polygon.rescale(page_size, image_size)
                if ocr_polygon.area > 0:
                    ocr_bbox_list.append(list(map(int, ocr_polygon.bbox)))
                    ocr_line_idx_list.append(line_idx)
            if len(ocr_bbox_list):
                ocr_bbox_page_list.append(ocr_bbox_list)
                ocr_page_line_idx_list.append(ocr_line_idx_list)
                page_id_list.append(page_id)

        recognition_results = run_recognition(
            images=[document.pages[i].highres_image for i in page_id_list],
            langs=[None] * len(page_id_list),
            rec_model=self.recognition_model,
            rec_processor=self.recognition_model.processor,
            bboxes=ocr_bbox_page_list,
            batch_size=int(self.get_recognition_batch_size())
        )

        page_spans = {}
        for (page_id, ocr_page_line_idxs, recognition_result) in zip(page_id_list, ocr_page_line_idx_list, recognition_results):
            if page_id not in page_spans:
                page_spans[page_id] = {}
            line_spans = page_spans[page_id]
            for ocr_line_idx, ocr_line in zip(ocr_page_line_idxs, recognition_result.text_lines):
                if ocr_line_idx not in line_spans:
                    line_spans[ocr_line_idx] = []
                line_spans[ocr_line_idx].append(Span(
                    text=ocr_line.text,
                    formats=['plain'],
                    page_id=page_id,
                    polygon=PolygonBox.from_bbox(ocr_line.bbox),
                    minimum_position=0,
                    maximum_position=0,
                    font='',
                    font_weight=0,
                    font_size=0,
                ))

        return page_spans

    def merge_blocks(self, document: Document, page_lines: PageLines, page_spans: PageSpans):
        ocred_pages = [page for page in document.pages if page.text_extraction_method == "surya"]
        for document_page, lines, line_spans in zip(ocred_pages, page_lines.values(), page_spans.values()):

            line_idxs = set(range(len(lines)))
            max_intersections = {}
            for line_idx, line in enumerate(lines):
                for block_idx, block in enumerate(document_page.children):
                    intersection_pct = line.polygon.intersection_pct(block.polygon)
                    if line_idx not in max_intersections:
                        max_intersections[line_idx] = (intersection_pct, block_idx)
                    elif intersection_pct > max_intersections[line_idx][0]:
                        max_intersections[line_idx] = (intersection_pct, block_idx)

            assigned_line_idxs = set()
            for line_idx, line in enumerate(lines):
                if line_idx in max_intersections and max_intersections[line_idx][0] > 0.0:
                    document_page.add_full_block(line)
                    block_idx = max_intersections[line_idx][1]
                    block: Block = document_page.children[block_idx]
                    block.add_structure(line)
                    block.polygon = block.polygon.merge([line.polygon])
                    block.text_extraction_method = "surya"
                    assigned_line_idxs.add(line_idx)
                    for span in line_spans[line_idx]:
                        document_page.add_full_block(span)
                        line.add_structure(span)

            for line_idx in line_idxs.difference(assigned_line_idxs):
                min_dist = None
                min_dist_idx = None
                line = lines[line_idx]
                for block_idx, block in enumerate(document_page.children):
                    dist = line.polygon.center_distance(block.polygon)
                    if min_dist_idx is None or dist < min_dist:
                        min_dist = dist
                        min_dist_idx = block_idx

                if min_dist_idx is not None:
                    document_page.add_full_block(line)
                    nearest_block = document_page.children[min_dist_idx]
                    nearest_block.add_structure(line)
                    nearest_block.polygon = nearest_block.polygon.merge([line.polygon])
                    nearest_block.text_extraction_method = "surya"
                    assigned_line_idxs.add(line_idx)
                    for span in line_spans[line_idx]:
                        document_page.add_full_block(span)
                        line.add_structure(span)
