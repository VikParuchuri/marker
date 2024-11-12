from typing import List

from surya.layout import batch_layout_detection
from surya.schema import LayoutResult

from marker.settings import settings
from marker.v2.builders import BaseBuilder
from marker.v2.schema.document import Document
from marker.v2.schema.groups.page import PageGroup


class LayoutBuilder(BaseBuilder):
    def __init__(self, layout_model, config):
        self.layout_model = layout_model

        super().__init__(config)

    def __call__(self, document: Document):
        layout_results = self.surya_layout(document.pages)
        self.add_blocks_to_pages(document.pages, layout_results)

    @classmethod
    def get_batch_size(cls):
        if settings.LAYOUT_BATCH_SIZE is not None:
            return settings.LAYOUT_BATCH_SIZE
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 6
        return 6

    def surya_layout(self, pages: List[PageGroup]) -> List[LayoutResult]:
        processor = self.layout_model.processor
        layout_results = batch_layout_detection(
            [p.lowres_image for p in pages],
            self.layout_model,
            processor,
            batch_size=int(LayoutBuilder.get_batch_size())
        )
        return layout_results

    def add_blocks_to_pages(self, pages: List[PageGroup], layout_results: List[LayoutResult]):
        for page, layout_result in zip(pages, layout_results):
            for bbox in sorted(layout_result.bboxes, key=lambda x: x.position):
                page.add_block(bbox.block_type, bbox.polygon)

