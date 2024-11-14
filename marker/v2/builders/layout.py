from typing import List

from surya.layout import batch_layout_detection
from surya.schema import LayoutResult

from marker.settings import settings
from marker.v2.builders import BaseBuilder
from marker.v2.providers.pdf import PdfProvider
from marker.v2.schema.blocks import LAYOUT_BLOCK_REGISTRY, Block, Text
from marker.v2.schema.document import Document
from marker.v2.schema.groups.page import PageGroup
from marker.v2.schema.polygon import PolygonBox
from marker.v2.schema.text.line import Line


class LayoutBuilder(BaseBuilder):
    def __init__(self, layout_model, config=None):
        self.layout_model = layout_model

        super().__init__(config)

    def __call__(self, document: Document, provider: PdfProvider):
        layout_results = self.surya_layout(document.pages)
        self.add_blocks_to_pages(document.pages, layout_results)
        self.merge_blocks(document.pages, provider)

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
                block_cls = LAYOUT_BLOCK_REGISTRY[bbox.label]
                layout_block = page.add_block(block_cls, PolygonBox(polygon=bbox.polygon))
                page.add_structure(layout_block)

    def merge_blocks(self, document_pages: List[PageGroup], provider: PdfProvider):
        provider_page_lines = provider.page_lines
        for idx, (document_page, provider_lines) in enumerate(zip(document_pages, provider_page_lines.values())):
            all_line_idxs = set(range(len(provider_lines)))
            page_size = provider.doc[idx].get_size()
            max_intersections = {}
            for line_idx, line in enumerate(provider_lines):
                for block_idx, block in enumerate(document_page.children):
                    line.polygon.rescale(page_size, document_page.polygon.size)
                    intersection_pct = line.polygon.intersection_pct(block.polygon)
                    if line_idx not in max_intersections:
                        max_intersections[line_idx] = (intersection_pct, block_idx)
                    elif intersection_pct > max_intersections[line_idx][0]:
                        max_intersections[line_idx] = (intersection_pct, block_idx)

            assigned_line_idxs = set()
            for line_idx, line in enumerate(provider_lines):
                if line_idx in max_intersections and max_intersections[line_idx][0] > 0.0:
                    document_page.add_full_block(line)
                    block_idx = max_intersections[line_idx][1]
                    block: Block = document_page.children[block_idx]
                    block.add_structure(line)
                    assigned_line_idxs.add(line_idx)

            for line_idx in all_line_idxs.difference(assigned_line_idxs):
                min_dist = None
                min_dist_idx = None
                line: Line = provider_lines[line_idx]
                for block_idx, block in enumerate(document_page.children):
                    dist = line.polygon.center_distance(block.polygon)
                    if min_dist_idx is None or dist < min_dist:
                        min_dist = dist
                        min_dist_idx = block_idx

                if min_dist_idx is not None:
                    document_page.add_full_block(line)
                    nearest_block = document_page.children[min_dist_idx]
                    nearest_block.add_structure(line)
                    assigned_line_idxs.add(line_idx)

            for line_idx in all_line_idxs.difference(assigned_line_idxs):
                line: Line = provider_lines[line_idx]
                document_page.add_full_block(line)
                # How do we add structure for when layout doesn't detect text?, squeeze between nearest block?
                text_block = document_page.add_block(Text, polygon=line.polygon)
                text_block.add_structure(line)
