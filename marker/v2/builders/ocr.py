from typing import List

from surya.ocr import run_recognition

from marker.settings import settings
from marker.v2.builders import BaseBuilder
from marker.v2.schema.blocks import BlockId
from marker.v2.schema.text.line import Line, Span
from marker.v2.schema.document import Document
from marker.v2.schema.groups.page import PageGroup
from marker.v2.schema.polygon import PolygonBox


class OcrBuilder(BaseBuilder):
    batch_size = None

    def __init__(self, ocr_model, config=None):
        self.ocr_model = ocr_model

        super().__init__(config)

    def __call__(self, document: Document):
        self.surya_recognition(document.pages)

    def get_batch_size(self):
        if self.batch_size is not None:
            return self.batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 32
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 32
        return 32

    def surya_recognition(self, pages: List[PageGroup]) -> List[List[str]]:
        ocr_bbox_list = []
        ocr_block_id_list: List[List[BlockId]] = []
        for page in pages:
            ocr_page_bbox_list = []
            ocr_page_block_id_list = []
            for block in page.children:
                if block.block_type in [
                    "Caption", "Code", "Footnote",
                    "Form", "Handwriting", "List-item",
                    "Page-footer", "Page-header",
                    "SectionHeader", "Text"
                ]:
                    if block.structure is None:
                        block.text_extraction_method = "surya"
                        block_polygon = block.polygon.rescale(page.polygon.size, page.highres_image.size)
                        bbox = list(map(round, block_polygon.bbox))
                        ocr_page_bbox_list.append(bbox)
                        ocr_page_block_id_list.append(block._id)
            ocr_bbox_list.append(ocr_page_bbox_list)
            ocr_block_id_list.append(ocr_page_block_id_list)

        recognition_results = run_recognition(
            images=[p.highres_image for p in pages],
            langs=[None] * len(pages),
            rec_model=self.ocr_model,
            rec_processor=self.ocr_model.processor,
            bboxes=ocr_bbox_list,
            batch_size=int(self.get_batch_size())
        )

        for ocr_block_ids, recognition_result in zip(ocr_block_id_list, recognition_results):
            for ocr_block_id, recognition in zip(ocr_block_ids, recognition_result.text_lines):
                page_id = ocr_block_id.page_id
                polygon = PolygonBox.from_bbox(recognition.bbox)
                page = pages[page_id]
                block = page.get_block(ocr_block_id)
                line_block = page.add_block(Line, polygon=polygon)
                block.add_structure(line_block)
                span_block = page.add_full_block(
                    Span(
                        text=recognition.text,
                        formats=['plain'],
                        page_id=page_id,
                        polygon=polygon,
                        minimum_position=0,
                        maximum_position=0,
                        font='',
                        font_weight=0,
                        font_size=0
                    )
                )
                line_block.add_structure(span_block)
