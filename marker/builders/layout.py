from typing import List

import numpy as np
from surya.layout import batch_layout_detection
from surya.schema import LayoutResult
from surya.model.layout.encoderdecoder import SuryaLayoutModel

from marker.settings import settings
from marker.builders import BaseBuilder
from marker.providers import ProviderOutput, ProviderPageLines
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.polygon import PolygonBox
from marker.schema.registry import get_block_class
from marker.util import matrix_intersection_area


class LayoutBuilder(BaseBuilder):
    """
    A builder for performing layout detection on PDF pages and merging the results into the document.

    Attributes:
        batch_size (int):
            The batch size to use for the layout model.
            Default is None, which will use the default batch size for the model.

        layout_coverage_min_lines (int):
            The minimum number of PdfProvider lines that must be covered by the layout model
            to consider the lines from the PdfProvider valid. Default is 1.

        layout_coverage_threshold (float):
            The minimum coverage ratio required for the layout model to consider
            the lines from the PdfProvider valid. Default is 0.3.

        document_ocr_threshold (float):
            The minimum ratio of pages that must pass the layout coverage check
            to avoid OCR. Default is 0.8.
    """
    batch_size = None
    layout_coverage_min_lines = 1
    layout_coverage_threshold = .1
    document_ocr_threshold = .8
    excluded_for_coverage = (BlockTypes.Figure, BlockTypes.Picture, BlockTypes.Table, BlockTypes.FigureGroup, BlockTypes.TableGroup, BlockTypes.PictureGroup)

    def __init__(self, layout_model: SuryaLayoutModel, config=None):
        self.layout_model = layout_model

        super().__init__(config)

    def __call__(self, document: Document, provider: PdfProvider):
        layout_results = self.surya_layout(document.pages)
        self.add_blocks_to_pages(document.pages, layout_results)
        self.merge_blocks(document.pages, provider.page_lines)

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
            page.layout_sliced = layout_result.sliced # This indicates if the page was sliced by the layout model
            for bbox in sorted(layout_result.bboxes, key=lambda x: x.position):
                block_cls = get_block_class(BlockTypes[bbox.label])
                layout_block = page.add_block(block_cls, PolygonBox(polygon=bbox.polygon))
                layout_block.polygon = layout_block.polygon.rescale(layout_page_size, provider_page_size)
                page.add_structure(layout_block)

            # Ensure page has non-empty structure
            if page.structure is None:
                page.structure = []

            # Ensure page has non-empty children
            if page.children is None:
                page.children = []

    def merge_blocks(self, document_pages: List[PageGroup], provider_page_lines: ProviderPageLines):
        good_pages = []
        for document_page in document_pages:
            provider_lines = provider_page_lines.get(document_page.page_id, [])
            good_pages.append(self.check_layout_coverage(document_page, provider_lines))

        ocr_document = sum(good_pages) / len(good_pages) < self.document_ocr_threshold
        for idx, document_page in enumerate(document_pages):
            provider_lines = provider_page_lines.get(document_page.page_id, [])
            needs_ocr = not good_pages[idx]

            if needs_ocr and ocr_document:
                document_page.text_extraction_method = "surya"
                continue
            document_page.merge_blocks(provider_lines, text_extraction_method="pdftext")
            document_page.text_extraction_method = "pdftext"

    def check_layout_coverage(
        self,
        document_page: PageGroup,
        provider_lines: List[ProviderOutput],
    ):
        covered_blocks = 0
        total_blocks = 0
        large_text_blocks = 0

        layout_blocks = [document_page.get_block(block) for block in document_page.structure]
        layout_blocks = [b for b in layout_blocks if b.block_type not in self.excluded_for_coverage]

        layout_bboxes = [block.polygon.bbox for block in layout_blocks]
        provider_bboxes = [line.line.polygon.bbox for line in provider_lines]

        intersection_matrix = matrix_intersection_area(layout_bboxes, provider_bboxes)

        for idx, layout_block in enumerate(layout_blocks):
            total_blocks += 1
            intersecting_lines = np.count_nonzero(intersection_matrix[idx] > 0)

            if intersecting_lines > self.layout_coverage_min_lines:
                covered_blocks += 1

            if layout_block.polygon.intersection_pct(document_page.polygon) > 0.8 and layout_block.block_type == BlockTypes.Text:
                large_text_blocks += 1

        coverage_ratio = covered_blocks / total_blocks if total_blocks > 0 else 1
        text_okay = coverage_ratio >= self.layout_coverage_threshold

        # Model will sometimes say there is a single block of text on the page when it is blank
        if not text_okay and (total_blocks == 1 and large_text_blocks == 1):
            text_okay = True
        return text_okay

