from copy import deepcopy
from typing import Annotated, List, Optional, Tuple

import numpy as np

from surya.detection import DetectionPredictor, InlineDetectionPredictor, TextDetectionResult
from surya.ocr_error import OCRErrorPredictor

from marker.builders import BaseBuilder
from marker.providers import ProviderOutput, ProviderPageLines
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.polygon import PolygonBox
from marker.schema.registry import get_block_class
from marker.schema.text.line import Line
from marker.settings import settings
from marker.util import matrix_intersection_area

class TextBox(PolygonBox):
    math: bool = False

    def __hash__(self):
        return hash(tuple(self.bbox))

class LineBuilder(BaseBuilder):
    """
    A builder for detecting text lines, and inline math. Merges the detected lines with the lines from the provider
    """
    detection_batch_size: Annotated[
        Optional[int],
        "The batch size to use for the detection model.",
        "Default is None, which will use the default batch size for the model."
    ] = None
    ocr_error_batch_size: Annotated[
        Optional[int],
        "The batch size to use for the ocr error detection model.",
        "Default is None, which will use the default batch size for the model."
    ] = None
    enable_table_ocr: Annotated[
        bool,
        "Whether to skip OCR on tables.  The TableProcessor will re-OCR them.  Only enable if the TableProcessor is not running.",
    ] = False
    layout_coverage_min_lines: Annotated[
        int,
        "The minimum number of PdfProvider lines that must be covered by the layout model",
        "to consider the lines from the PdfProvider valid.",
    ] = 1
    layout_coverage_threshold: Annotated[
        float,
        "The minimum coverage ratio required for the layout model to consider",
        "the lines from the PdfProvider valid.",
    ] = .25
    document_ocr_threshold: Annotated[
        float,
        "The minimum ratio of pages that must pass the layout coverage check",
        "to avoid OCR.",
    ] = .8
    detected_provider_line_overlap: Annotated[
        float,
        "The maximum overlap between a detected text line and a provider line to consider as a new line"
    ] = .3
    span_inline_math_overlap_threshold: Annotated[
        float,
        "The minimum overlap of a span with an inline math box to consider for removal"
    ] = .5
    char_inline_math_overlap_threshold: Annotated[
        float,
        "The minimum overlap of a character with an inline math box to consider for removal"
    ] = .5
    line_inline_math_overlap_threshold: Annotated[
        float,
        "The minimum overlap of a line with an inline math box to consider as a match"
    ] = 0.
    inline_math_minimum_area: Annotated[
        float,
        "The minimum area for an inline math block, in pixels."
    ] = 20
    excluded_for_coverage: Annotated[
        Tuple[BlockTypes],
        "A list of block types to exclude from the layout coverage check.",
    ] = (BlockTypes.Figure, BlockTypes.Picture, BlockTypes.Table, BlockTypes.FigureGroup, BlockTypes.TableGroup, BlockTypes.PictureGroup)

    def __init__(self, detection_model: DetectionPredictor, inline_detection_model: InlineDetectionPredictor, ocr_error_model: OCRErrorPredictor, config=None):
        super().__init__(config)

        self.detection_model = detection_model
        self.inline_detection_model = inline_detection_model
        self.ocr_error_model = ocr_error_model

    def __call__(self, document: Document, provider: PdfProvider):
        # Disable Inline Detection for documents where layout model doesn't detect any equations
        do_inline_math_detection = document.contained_blocks([BlockTypes.Equation])
        provider_lines, ocr_lines = self.get_all_lines(document, provider, do_inline_math_detection)
        self.merge_blocks(document, provider_lines, ocr_lines)

    def get_detection_batch_size(self):
        if self.detection_batch_size is not None:
            return self.detection_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 4
        return 4

    def get_ocr_error_batch_size(self):
        if self.ocr_error_batch_size is not None:
            return self.ocr_error_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 4
        return 4

    def get_all_lines(self, document: Document, provider: PdfProvider, do_inline_math_detection: bool):
        page_images = [page.get_image(highres=False, remove_tables=not self.enable_table_ocr) for page in document.pages]
        detection_results = self.detection_model(
            images=page_images,
        )
        ocr_error_detection_results = self.ocr_error_detection(document.pages, provider.page_lines)

        inline_detection_results = [None] * len(page_images)
        if do_inline_math_detection:
            inline_detection_results = self.inline_detection_model(
                images=page_images,
                text_boxes=[[b.bbox for b in det_result.bboxes] for det_result in detection_results]
            )

        boxes_to_ocr = {page.page_id: [] for page in document.pages}
        page_lines = {page.page_id: [] for page in document.pages}

        LineClass: Line = get_block_class(BlockTypes.Line)

        for document_page, detection_result, inline_detection_result, ocr_error_detection_label in zip(
                document.pages,
                detection_results,
                inline_detection_results,
                ocr_error_detection_results.labels
        ):
            provider_lines: List[ProviderOutput] = provider.page_lines.get(document_page.page_id, [])
            image_size = PolygonBox.from_bbox(detection_result.image_bbox).size
            page_size = provider.get_page_bbox(document_page.page_id).size

            # Filter out detected equation blocks
            inline_detection_result = self.filter_equation_overlaps(
                document,
                document_page,
                inline_detection_result,
                image_size,
                page_size
            )

            # Merge text and inline math detection results
            merged_detection_boxes = self.determine_math_lines(text_result=detection_result, inline_result=inline_detection_result)
            math_detection_boxes = [box for box in merged_detection_boxes if box.math]
            nonmath_detection_boxes = [box for box in merged_detection_boxes if not box.math]

            provider_lines_good = all([
                bool(provider),
                ocr_error_detection_label != 'bad',
                self.check_layout_coverage(document_page, provider_lines)
            ])

            if provider_lines_good:
                # Merge inline math blocks into the provider lines, only persist new detected text lines which do not overlap with existing provider lines
                # The missing lines are not from a table, so we can safely set this - The attribute for individual blocks is overidden by OCRBuilder
                document_page.text_extraction_method = 'pdftext'

                # OCR any lines that don't overlap with a provider line
                boxes_to_ocr[document_page.page_id].extend(
                    self.filter_detected_text_lines(provider_lines, nonmath_detection_boxes, image_size, page_size)
                )

                # Add in the provider lines - merge ones that get broken by inline math
                page_lines[document_page.page_id].extend(
                    self.merge_provider_lines_inline_math(document_page.page_id, provider_lines, math_detection_boxes, image_size, page_size)
                )
            else:
                document_page.text_extraction_method = 'surya'

                # Skip inline math merging if no provider lines are good; OCR all text lines and all inline math lines
                boxes_to_ocr[document_page.page_id].extend(nonmath_detection_boxes + math_detection_boxes)

        # Dummy lines to merge into the document - Contains no spans, will be filled in later by OCRBuilder
        ocr_lines = {document_page.page_id: [] for document_page in document.pages}
        for page_id, page_ocr_boxes in boxes_to_ocr.items():
            page_size = provider.get_page_bbox(page_id).size
            image_size = document.get_page(page_id).get_image(highres=False, remove_tables=not self.enable_table_ocr).size
            for box_to_ocr in page_ocr_boxes:
                line_polygon = PolygonBox(polygon=box_to_ocr.polygon).rescale(image_size, page_size)
                format = ["math"] if box_to_ocr.math else None
                ocr_lines[page_id].append(
                    ProviderOutput(
                        line=LineClass(
                            polygon=line_polygon,
                            page_id=page_id,
                            text_extraction_method='surya',
                            formats=format
                        ),
                        spans=[]
                    )
                )

        return page_lines, ocr_lines

    def ocr_error_detection(self, pages:List[PageGroup], provider_page_lines: ProviderPageLines):
        page_texts = []
        for document_page in pages:
            provider_lines = provider_page_lines.get(document_page.page_id, [])
            page_text = '\n'.join(' '.join(s.text for s in line.spans) for line in provider_lines)
            page_texts.append(page_text)

        ocr_error_detection_results = self.ocr_error_model(
            page_texts,
            batch_size=int(self.get_ocr_error_batch_size())
        )
        return ocr_error_detection_results

    def filter_detected_text_lines(
            self,
            provider_lines: List[ProviderOutput],
            detected_text_lines: List[TextBox],
            image_size,
            page_size
    ):
        filtered_lines = []
        rescaled_line_boxes = [PolygonBox(polygon=line.polygon).rescale(image_size, page_size).bbox for line in detected_text_lines]
        intersections = matrix_intersection_area(rescaled_line_boxes, [line.line.polygon.bbox for line in provider_lines])
        for detected_line, intersection in zip(detected_text_lines, intersections):
            max_intersection = np.max(intersection) / detected_line.area
            if max_intersection < self.detected_provider_line_overlap:
                filtered_lines.append(detected_line)
        
        return filtered_lines

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

            if intersecting_lines >= self.layout_coverage_min_lines:
                covered_blocks += 1

            if layout_block.polygon.intersection_pct(document_page.polygon) > 0.8 and layout_block.block_type == BlockTypes.Text:
                large_text_blocks += 1

        coverage_ratio = covered_blocks / total_blocks if total_blocks > 0 else 1
        text_okay = coverage_ratio >= self.layout_coverage_threshold

        # Model will sometimes say there is a single block of text on the page when it is blank
        if not text_okay and (total_blocks == 1 and large_text_blocks == 1):
            text_okay = True
        return text_okay

    def merge_blocks(self, document: Document, page_provider_lines: ProviderPageLines, page_ocr_lines: ProviderPageLines):
        def reading_order(line1, line2):
            """
            Determines the reading order between two lines, assuming lists of lines are already individually in reading order
            """
            poly1, poly2 = line1.line.polygon, line2.line.polygon

            vertical_overlap = poly1.overlap_y(poly2)
            avg_height = (poly1.height + poly2.height) / 2

            if vertical_overlap > 0.5 * avg_height:
                return poly1.x_start - poly2.x_start  # Left-to-right order
            return poly1.y_start - poly2.y_start  # Top-to-bottom order

        for document_page in document.pages:
            provider_lines = page_provider_lines[document_page.page_id]
            ocr_lines = page_ocr_lines[document_page.page_id]

            merged_lines = []
            i, j = 0, 0

            while i < len(provider_lines) and j < len(ocr_lines):
                if reading_order(provider_lines[i], ocr_lines[j]) <= 0:
                    merged_lines.append(provider_lines[i])
                    i += 1
                else:
                    merged_lines.append(ocr_lines[j])
                    j += 1

            merged_lines.extend(provider_lines[i:])
            merged_lines.extend(ocr_lines[j:])

            # Text extraction method is overidden later for OCRed documents
            document_page.merge_blocks(merged_lines, text_extraction_method='pdftext')

    def filter_equation_overlaps(
            self,
            document,
            page: PageGroup,
            inline_boxes: TextDetectionResult,
            image_size,
            page_size
    ):
        if inline_boxes is None:
            return inline_boxes

        equations = page.contained_blocks(document, (BlockTypes.Equation,))
        equation_boxes = [eq.polygon.bbox for eq in equations]
        inline_bboxes = [PolygonBox(polygon=box.polygon).rescale(image_size, page_size).bbox for box in inline_boxes.bboxes]

        if len(equation_boxes) == 0 or len(inline_bboxes) == 0:
            return inline_boxes

        overlaps = matrix_intersection_area(inline_bboxes, equation_boxes)
        overlap_idxs = np.max(overlaps, axis=-1) > self.line_inline_math_overlap_threshold
        inline_boxes.bboxes = [ib for i, ib in enumerate(inline_boxes.bboxes) if not overlap_idxs[i]]
        return inline_boxes


    def determine_math_lines(
        self,
        text_result: TextDetectionResult,
        inline_result: TextDetectionResult,
    ) -> List[TextBox]:
        """
        Marks lines as math if they contain inline math boxes.
        """

        text_boxes = [
            TextBox(
                polygon=box.polygon
            ) for box in text_result.bboxes
        ]
        
        # Skip if no inline math was detected
        if not inline_result:
            return text_boxes

        inline_bboxes = [m.bbox for m in inline_result.bboxes]
        text_bboxes = [t.bbox for t in text_boxes]
        overlaps = matrix_intersection_area(inline_bboxes, text_bboxes)

        # Mark text boxes as math if they overlap with an inline math box
        for i, inline_box in enumerate(inline_result.bboxes):
            overlap_row = overlaps[i]
            max_overlap_idx = np.argmax(overlap_row)
            max_overlap_box = text_boxes[max_overlap_idx]

            max_overlap = np.max(overlap_row) / inline_box.area

            # Avoid small or nonoverlapping inline math regions
            if max_overlap <= self.line_inline_math_overlap_threshold or inline_box.area < self.inline_math_minimum_area:
                continue

            # Ignore vertical lines
            if max_overlap_box.height > max_overlap_box.width:
                continue

            max_overlap_box.math = True

        return text_boxes

    # Add appropriate formats to math spans added by inline math detection
    def add_math_span_format(self, provider_line):
        if not provider_line.line.formats:
            provider_line.line.formats = ["math"]
        elif "math" not in provider_line.line.formats:
            provider_line.line.formats.append("math")

    def merge_provider_lines_inline_math(
            self,
            document_page_id,
            provider_lines: List[ProviderOutput],
            inline_math_lines: List[TextBox],
            image_size,
            page_size
    ):
        # When provider lines is empty or no inline math detected, return provider lines
        if not provider_lines or not inline_math_lines:
            return provider_lines

        horizontal_provider_lines = [(j, provider_line) for j, provider_line in enumerate(provider_lines) if provider_line.line.polygon.height < provider_line.line.polygon.width]
        provider_line_boxes = [p.line.polygon.bbox for _, p in horizontal_provider_lines]
        math_line_boxes = [PolygonBox(polygon=m.polygon).rescale(image_size, page_size).bbox for m in inline_math_lines]

        overlaps = matrix_intersection_area(math_line_boxes, provider_line_boxes)

        # Find potential merges
        merge_lines = []
        for i in range(len(math_line_boxes)):
            merge_line = []
            math_line_polygon = PolygonBox(polygon=inline_math_lines[i].polygon).rescale(image_size, page_size)
            max_overlap = np.max(overlaps[i])
            if max_overlap <= self.line_inline_math_overlap_threshold:
                continue

            nonzero_idxs = np.nonzero(overlaps[i] > self.line_inline_math_overlap_threshold)[0]
            for idx in nonzero_idxs:
                provider_idx, provider_line = horizontal_provider_lines[idx]
                line_overlaps = self.check_char_math_overlap(provider_line, math_line_polygon)
                if line_overlaps:
                    # Add the index of the provider line to the merge line
                    merge_line.append(provider_idx)

            if len(merge_line) > 0:
                merge_lines.append(merge_line)

        # Handle the merging
        already_merged = set()
        potential_merges = set([m for merge_line in merge_lines for m in merge_line])
        out_provider_lines = [(i, p) for i, p in enumerate(provider_lines) if i not in potential_merges]
        for merge_section in merge_lines:
            merge_section = [m for m in merge_section if m not in already_merged]
            if len(merge_section) == 0:
                continue
            elif len(merge_section) == 1:
                line_idx = merge_section[0]
                merged_line = provider_lines[line_idx]
                self.add_math_span_format(merged_line)
                out_provider_lines.append((line_idx, merged_line))
                already_merged.add(merge_section[0])
                continue

            merge_section = sorted(merge_section)
            merged_line = None
            min_idx = min(merge_section)
            for idx in merge_section:
                provider_line = deepcopy(provider_lines[idx])
                if merged_line is None:
                    merged_line = provider_line
                else:
                    # Combine the spans of the provider line with the merged line
                    merged_line = merged_line.merge(provider_line)
                    self.add_math_span_format(merged_line)
            out_provider_lines.append((min_idx, merged_line))

        # Sort to preserve original order
        out_provider_lines = sorted(out_provider_lines, key=lambda x: x[0])
        out_provider_lines = [p for _, p in out_provider_lines]
        return out_provider_lines

    def check_char_math_overlap(self, provider_line, math_line_polygon):
        # Identify if a character in the provider line overlaps with the inline math line - meaning that the line can be treated as math
        spans = provider_line.spans
        math_overlaps = False

        # For providers which do not surface characters
        if provider_line.chars is None:
            for span in spans:
                if span.polygon.intersection_pct(math_line_polygon) > self.span_inline_math_overlap_threshold:
                    math_overlaps = True
            return math_overlaps

        # For providers which surface characters - find line overlap based on characters
        assert len(spans) == len(provider_line.chars), "Number of spans and characters in provider line do not match"
        for span, span_chars in zip(spans, provider_line.chars):
            for char in span_chars:
                if char.polygon.intersection_pct(math_line_polygon) >= self.char_inline_math_overlap_threshold:
                    return True

        return math_overlaps