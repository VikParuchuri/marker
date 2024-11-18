from typing import List

from surya.layout import batch_layout_detection
from surya.schema import LayoutResult

from marker.settings import settings
from marker.v2.builders import BaseBuilder
from marker.v2.providers.pdf import PageLines, PageSpans, PdfProvider
from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import LAYOUT_BLOCK_REGISTRY, Block, Text
from marker.v2.schema.document import Document
from marker.v2.schema.groups.page import PageGroup
from marker.v2.schema.polygon import PolygonBox
from marker.v2.schema.text.line import Line


class LayoutBuilder(BaseBuilder):
    batch_size = None

    def __init__(self, layout_model, config=None):
        self.layout_model = layout_model

        super().__init__(config)

    def __call__(self, document: Document, provider: PdfProvider):
        layout_results = self.surya_layout(document.pages)
        self.add_blocks_to_pages(document.pages, layout_results)
        self.merge_blocks(document.pages, provider.page_lines, provider.page_spans)

    def get_batch_size(self):
        if self.batch_size is not None:
            return self.batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 6
        return 6

    def surya_layout(self, pages: List[PageGroup]) -> List[LayoutResult]:
        processor = self.layout_model.processor
        layout_results = batch_layout_detection(
            [p.lowres_image for p in pages],
            self.layout_model,
            processor,
            batch_size=int(self.get_batch_size())
        )
        return layout_results

    def add_blocks_to_pages(self, pages: List[PageGroup], layout_results: List[LayoutResult]):
        for page, layout_result in zip(pages, layout_results):
            layout_page_size = PolygonBox.from_bbox(layout_result.image_bbox).size
            provider_page_size = page.polygon.size
            for bbox in sorted(layout_result.bboxes, key=lambda x: x.position):
                block_cls = LAYOUT_BLOCK_REGISTRY[BlockTypes[bbox.label]]
                layout_block = page.add_block(block_cls, PolygonBox(polygon=bbox.polygon))
                layout_block.polygon = layout_block.polygon.rescale(layout_page_size, provider_page_size)
                page.add_structure(layout_block)

    def merge_blocks(self, document_pages: List[PageGroup], provider_page_lines: PageLines, provider_page_spans: PageSpans):
        for document_page, provider_lines in zip(document_pages, provider_page_lines.values()):
            if not self.check_layout_coverage(document_page, provider_lines):
                document_page.text_extraction_method = "surya"
                continue

            line_spans = provider_page_spans[document_page.page_id]
            provider_line_idxs = set(range(len(provider_lines)))
            max_intersections = {}
            for line_idx, line in enumerate(provider_lines):
                for block_idx, block in enumerate(document_page.children):
                    if block.block_type in [BlockTypes.Line, BlockTypes.Span]:
                        continue
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
                    block.polygon = block.polygon.merge([line.polygon])
                    block.text_extraction_method = "pdftext"
                    assigned_line_idxs.add(line_idx)
                    for span in line_spans[line_idx]:
                        document_page.add_full_block(span)
                        line.add_structure(span)

            for line_idx in provider_line_idxs.difference(assigned_line_idxs):
                min_dist = None
                min_dist_idx = None
                line = provider_lines[line_idx]
                for block_idx, block in enumerate(document_page.children):
                    if block.block_type in [BlockTypes.Line, BlockTypes.Span]:
                        continue
                    dist = line.polygon.center_distance(block.polygon)
                    if min_dist_idx is None or dist < min_dist:
                        min_dist = dist
                        min_dist_idx = block_idx

                if min_dist_idx is not None:
                    document_page.add_full_block(line)
                    nearest_block = document_page.children[min_dist_idx]
                    nearest_block.add_structure(line)
                    nearest_block.polygon = nearest_block.polygon.merge([line.polygon])
                    nearest_block.text_extraction_method = "pdftext"
                    assigned_line_idxs.add(line_idx)
                    for span in line_spans[line_idx]:
                        document_page.add_full_block(span)
                        line.add_structure(span)

    def check_layout_coverage(
        self,
        document_page: PageGroup,
        provider_lines: List[Line],
        coverage_threshold=0.5
    ):
        layout_area = 0
        provider_area = 0
        for layout_block_id in document_page.structure:
            layout_block = document_page.get_block(layout_block_id)
            if layout_block.block_type in [BlockTypes.Figure, BlockTypes.Picture, BlockTypes.Table]:
                continue
            layout_area += layout_block.polygon.area
            for provider_line in provider_lines:
                provider_area += layout_block.polygon.intersection_area(provider_line.polygon)
        coverage_ratio = provider_area / layout_area if layout_area > 0 else 0
        return coverage_ratio >= coverage_threshold
