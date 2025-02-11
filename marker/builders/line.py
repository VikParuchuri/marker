from typing import Annotated, List, Optional, Tuple

from ftfy import fix_text
import numpy as np
from collections import defaultdict

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
from marker.schema.text.span import Span
from marker.settings import settings
from marker.util import matrix_intersection_area

class TextBox(PolygonBox):
    math: bool =False
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
    enable_inline_math_detection: Annotated[
        bool,
        "Whether to detect inline math separately to replace with latex. Only enable if EquationProcessor is also running."
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
    ] = .1
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
        "The minimum overlap of a provider line with an inline math box to consider as a match"
    ] = 0.
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
        #Disable Inline Detection for documents where layout model doesn't detect any equations
        self.enable_inline_math_detection = self.enable_inline_math_detection and document.contained_blocks([BlockTypes.Equation])
        provider_lines, ocr_lines= self.get_all_lines(document, provider)
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

    def get_all_lines(self, document: Document, provider: PdfProvider):
        page_images = [page.get_image(highres=False, remove_tables=not self.enable_table_ocr) for page in document.pages]
        detection_results = self.detection_model(
            images=page_images,
        )
        ocr_error_detection_results = self.ocr_error_detection(document.pages, provider.page_lines)
        if self.enable_inline_math_detection:
            inline_detection_results = self.inline_detection_model(
                images=page_images,
                text_boxes=[[b.bbox for b in det_result.bboxes] for det_result in detection_results]
            )
        else:
            inline_detection_results = [TextDetectionResult(
                bboxes=[],
                vertical_lines=[],
                heatmap=None,
                affinity_map=None,
                image_bbox=[]
            )]*len(page_images)

        boxes_to_ocr = {page.page_id: [] for page in document.pages}
        page_lines = {page.page_id: [] for page in document.pages}

        SpanClass: Span = get_block_class(BlockTypes.Span)
        LineClass: Line = get_block_class(BlockTypes.Line)

        for document_page, detection_result, inline_detection_result, ocr_error_detection_label in zip(document.pages, detection_results, inline_detection_results, ocr_error_detection_results.labels):
            provider_lines = provider.page_lines.get(document_page.page_id, [])
            detection_result_split = self.split_detected_text_and_inline_boxes(text_boxes=[box for box in detection_result.bboxes], inline_boxes=[box for box in inline_detection_result.bboxes])
            detected_text_lines = [box for box in detection_result_split if not box.math]
            detected_inline_math_lines = [box for box in detection_result_split if box.math]

            image_size = PolygonBox.from_bbox(detection_result.image_bbox).size
            page_size = provider.get_page_bbox(document_page.page_id).size

            provider_lines_good = bool(provider) and ocr_error_detection_label!='bad' and self.check_layout_coverage(document_page, provider_lines)

            if provider_lines_good:
                # Merge inline math blocks into the provider lines, only persist new detected text lines which do not overlap with existing provider lines
                #The missing lines are not from a table, so we can safely set this - The attribute for individual blocks is overidden by OCRBuilder
                document_page.text_extraction_method = 'pdftext'        
                boxes_to_ocr[document_page.page_id].extend(self.filter_detected_text_lines(provider_lines, detected_text_lines, image_size, page_size))
                page_lines[document_page.page_id].extend(self.merge_provider_lines_inline_math(document_page.page_id, provider_lines, detected_inline_math_lines, image_size, page_size))
                continue

            document_page.text_extraction_method = 'surya'
            #Skip inline math merging if no provider lines are good; OCR all text lines and all inline math lines
            boxes_to_ocr[document_page.page_id].extend(detected_text_lines)
            for line in detected_inline_math_lines:
                polygon = PolygonBox.from_bbox(line.bbox).rescale(image_size, page_size)
                line = LineClass(
                    polygon=polygon,
                    page_id=document_page.page_id,
                )
                spans = [
                    SpanClass(
                        text="",
                        formats=['math'],
                        page_id=document_page.page_id,
                        polygon=polygon,
                        minimum_position=0,
                        maximum_position=0,
                        font='Unknown',
                        font_weight=0,
                        font_size=0,
                    )
                ]

                page_lines[document_page.page_id].append(ProviderOutput(line=line, spans=spans))

        #Dummy lines to merge into the document - Contains no spans, will be filled in later by OCRBuilder
        ocr_lines = {document_page.page_id: [] for document_page in document.pages}
        for page_id, page_ocr_boxes in boxes_to_ocr.items():
            page_size = provider.get_page_bbox(page_id).size
            image_size = document.get_page(page_id).get_image(highres=False, remove_tables=not self.enable_table_ocr).size
            for box_to_ocr in page_ocr_boxes:
                line_polygon = PolygonBox(polygon=box_to_ocr.polygon).rescale(image_size, page_size)
                ocr_lines[page_id].append(
                    ProviderOutput(
                        line=LineClass(
                            polygon=line_polygon,
                            page_id=page_id,
                            text_extraction_method='surya'
                        ),
                        spans=[]
                    )
                )

        return page_lines, ocr_lines

    def ocr_error_detection(self, pages:List[PageGroup], provider_page_lines: ProviderPageLines):
        page_texts = []
        for document_page in pages:
            page_text = ''
            provider_lines = provider_page_lines.get(document_page.page_id, [])
            page_text = '\n'.join(' '.join(s.text for s in line.spans) for line in provider_lines)
            page_texts.append(page_text)

        ocr_error_detection_results = self.ocr_error_model(
            page_texts,
            batch_size=int(self.get_ocr_error_batch_size())
        )
        return ocr_error_detection_results

    def filter_detected_text_lines(self, provider_lines, detected_text_lines, image_size, page_size):
        filtered_lines = []
        for detected_line in detected_text_lines:
            keep_line = True
            detected_line_polygon = PolygonBox(polygon=detected_line.polygon).rescale(image_size, page_size)
            detected_line_area = detected_line_polygon.area
            for provider_line in provider_lines:
                intersection_area = provider_line.line.polygon.intersection_area(detected_line_polygon)
                if detected_line_area > 0 and (intersection_area / detected_line_area) > self.detected_provider_line_overlap:
                    keep_line = False
                    break
            
            if keep_line:
                filtered_lines.append(detected_line)
        
        return filtered_lines

    #Add appropriate formats to math spans added by inline math detection - Useful for when the span is skipped by EquationProcessor
    def fix_span_formats(self, provider_line):
        for idx, span in enumerate(provider_line.spans):
            if 'math' in span.formats:
                prev_formats = [] if idx==0 else provider_line.spans[idx-1].formats
                next_formats = [] if idx==len(provider_line.spans)-1 else provider_line.spans[idx+1].formats
                if not prev_formats or not next_formats or prev_formats==next_formats:      #Matching formats, accounting for current span being start/end
                    span.formats += prev_formats
                    span.formats += next_formats
                span.formats = list(set(span.formats))

    def merge_provider_lines_inline_math(self, document_page_id, provider_lines, inline_math_lines, image_size, page_size):
        #When provider lines is empty
        if not provider_lines:
            return provider_lines
        
        #When no inline math is detected
        if not inline_math_lines:
            return provider_lines

        updated_provider_lines = []
        provider_line_to_inline = {provider_line: [] for provider_line in provider_lines}
        inline_math_removed_text = defaultdict(str)

        for math_line in inline_math_lines:
            math_line_polygon = PolygonBox(polygon=math_line.polygon).rescale(image_size, page_size)
            math_line_area = math_line_polygon.area
            if math_line_area == 0:
                continue
            
            best_match = None
            best_overlap = self.line_inline_math_overlap_threshold

            for provider_line in provider_lines:
                if provider_line.line.polygon.height>provider_line.line.polygon.width:
                    continue
                overlap = provider_line.line.polygon.intersection_area(math_line_polygon) / math_line_area
                if overlap>self.line_inline_math_overlap_threshold:
                    line_removed_text = self._reconstruct_provider_line(provider_line, math_line_polygon)
                    inline_math_removed_text[math_line] += line_removed_text
                    pass
                if overlap>best_overlap:
                    best_overlap = overlap
                    best_match = provider_line
                
            if best_match:
                provider_line_to_inline[best_match].append(math_line)

        for provider_line, math_lines in provider_line_to_inline.items():
            #No intersection with math, or vertical text line - Skip
            if not math_lines or provider_line.line.polygon.height>provider_line.line.polygon.width:
                updated_provider_lines.append(provider_line)
                continue

            new_spans = provider_line.spans
            #Add math lines in as new spans - Empty text to be replaced with latex by EquationProcessor later
            SpanClass: Span = get_block_class(BlockTypes.Span)
            for math_line in math_lines:
                new_spans.append(
                    SpanClass(
                        text=inline_math_removed_text[math_line],
                        formats=['math'],
                        page_id=document_page_id,
                        polygon=PolygonBox(polygon=math_line.polygon).rescale(image_size, page_size),
                        minimum_position=0,
                        maximum_position=0,
                        font='Unknown',
                        font_weight=0,
                        font_size=0,
                    )
                )
            provider_line.spans = sorted(new_spans, key=lambda s:s.polygon.x_start)
            self.fix_span_formats(provider_line)
            updated_provider_lines.append(provider_line)

        return updated_provider_lines

    def _reconstruct_provider_line(self, provider_line, math_line_polygon):
        spans_to_keep = []
        spans = provider_line.spans
        SpanClass: Span = get_block_class(BlockTypes.Span)

        #For providers which do not surface characters
        if provider_line.chars is None:
            removed_text = ""
            for span in spans:
                if span.polygon.intersection_pct(math_line_polygon)<self.span_inline_math_overlap_threshold:
                    spans_to_keep.append(span)
                else:
                    removed_text += span.text
            provider_line.spans = spans_to_keep
            return removed_text.strip()

        #For providers which surface characters - Split the span based on overlapping characters
        removed_text = ""
        chars_to_keep = []
        assert len(spans) == len(provider_line.chars)
        for span, span_chars in zip(spans, provider_line.chars):
            if span.polygon.intersection_area(math_line_polygon)==0:
                spans_to_keep.append(span)
                chars_to_keep.append(span_chars)
                continue
            #Split at the inline math
            left_chars, right_chars = [], []
            math_line_center_x = math_line_polygon.center[0]

            for char in span_chars:
                if char.polygon.intersection_pct(math_line_polygon)>=self.char_inline_math_overlap_threshold:
                    removed_text += char.char
                    continue  # Skip characters that overlap with the math polygon
                
                # Since chars are already in left-to-right order, we can just check position
                if char.polygon.center[0] < math_line_center_x:
                    left_chars.append(char)
                else:
                    right_chars.append(char)

            if left_chars:
                left_polygon = left_chars[0].polygon.merge([c.polygon for c in left_chars])
                spans_to_keep.append(SpanClass(
                    text=fix_text(''.join(c.char for c in left_chars)),
                    formats=span.formats,
                    page_id=span.page_id,
                    polygon=left_polygon,
                    minimum_position=left_chars[0].char_idx,
                    maximum_position=left_chars[-1].char_idx,
                    font=span.font,
                    font_weight=span.font_weight,
                    font_size=span.font_size
                ))
                chars_to_keep.append(left_chars)
            if right_chars:
                right_polygon = right_chars[0].polygon.merge([c.polygon for c in right_chars])
                spans_to_keep.append(SpanClass(
                    text=fix_text(''.join(c.char for c in right_chars)),
                    formats=span.formats,
                    page_id=span.page_id,
                    polygon=right_polygon,
                    minimum_position=right_chars[0].char_idx,
                    maximum_position=right_chars[-1].char_idx,
                    font=span.font,
                    font_weight=span.font_weight,
                    font_size=span.font_size
                ))
                chars_to_keep.append(right_chars)
        provider_line.spans = spans_to_keep
        provider_line.chars = chars_to_keep

        return removed_text


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

            #Text extraction method is overidden later for OCRed documents
            document_page.merge_blocks(merged_lines, text_extraction_method='pdftext')

    def split_detected_text_and_inline_boxes(
        self,
        text_boxes: List[PolygonBox], 
        inline_boxes: List[PolygonBox], 
    ) -> List[TextBox]:
        """
        Splits horizontal text boxes around inline boxes, skips vertical text boxes, 
        and retains unrelated text boxes.
        """
        
        #Skip if no inline math was detected
        if not inline_boxes:
            return [TextBox(polygon=text_box.polygon, confidence=text_box.confidence, math=False) for text_box in text_boxes]

        result_boxes = []  # Final result to store the split boxes and retained boxes
        horizontal_text_boxes = []  # Only horizontal text boxes to process

        # Step 1: Separate vertical and horizontal text boxes
        for text_box in text_boxes:
            if text_box.height > text_box.width:
                # Retain vertical text boxes
                result_boxes.append(TextBox(
                    polygon=text_box.polygon,
                    confidence=text_box.confidence
                ))
            else:
                horizontal_text_boxes.append(text_box)

        # Step 2: Assign inline boxes to horizontal text boxes
        inline_assignments = {inline_box: None for inline_box in inline_boxes}

        for inline_box in inline_boxes:
            max_overlap_ratio = 0.3     #Need atleast this much overlap to even consider assignment at all
            assigned_text_box = None

            for text_box in horizontal_text_boxes:
                # Calculate intersection area
                intersection_area = text_box.intersection_area(inline_box)

                # Calculate overlap ratios
                inline_overlap_ratio = intersection_area / inline_box.area if inline_box.area > 0 else 0
                text_overlap_ratio = intersection_area / text_box.area if text_box.area > 0 else 0

                # Check if the inline box fully covers the text box
                if text_overlap_ratio == 1:
                    # Fully covered text box: Remove it and retain only the inline box
                    if text_box in horizontal_text_boxes:
                        horizontal_text_boxes.remove(text_box)
                    inline_assignments[inline_box] = None
                elif inline_overlap_ratio > max_overlap_ratio:
                    # Assign inline box to the text box with the highest overlap ratio
                    max_overlap_ratio = inline_overlap_ratio
                    assigned_text_box = text_box

            # Assign inline box to the selected text box (if not fully covering)
            if assigned_text_box:
                inline_assignments[inline_box] = assigned_text_box


        for text_box in horizontal_text_boxes:
            # Get all inline boxes assigned to this text box
            assigned_inline_boxes = [
                inline_box for inline_box, assigned_text in inline_assignments.items() if assigned_text == text_box
            ]

            if not assigned_inline_boxes:
                # Retain the text box if it is not intersected by any inline boxes
                result_boxes.append(TextBox(
                    polygon=text_box.polygon,
                    confidence=text_box.confidence
                ))
                continue
            # Sort assigned inline boxes from left to right
            assigned_inline_boxes.sort(key=lambda box: box.bbox[0])

            current_x1 = text_box.bbox[0]  # Start with the leftmost x-coordinate of the text box
            y1_t, y2_t = min(box.bbox[1] for box in [text_box]+assigned_inline_boxes), max(box.bbox[3] for box in [text_box]+assigned_inline_boxes)
            text_segments = []

            for inline_box in assigned_inline_boxes:
                x1_i, x2_i = inline_box.bbox[0], inline_box.bbox[2]

                # Add the text segment before the inline box, if any
                if current_x1 < x1_i:
                    text_segments.append(TextBox(
                        polygon=[
                            [current_x1, y1_t],
                            [x1_i, y1_t],
                            [x1_i, y2_t],
                            [current_x1, y2_t],
                        ],
                        confidence=text_box.confidence
                    ))

                # Add the inline box itself
                text_segments.append(TextBox(
                    polygon=[
                        [x1_i, y1_t],
                        [x2_i, y1_t],
                        [x2_i, y2_t],
                        [x1_i, y2_t],
                    ],
                    confidence=inline_box.confidence,
                    math=True
                ))
                current_x1 = x2_i  # Move the start point to after the current inline box

            # Add any remaining text after the last inline box, if any
            if current_x1 < text_box.bbox[2]:
                text_segments.append(TextBox(
                    polygon=[
                        [current_x1, y1_t],
                        [text_box.bbox[2], y1_t],
                        [text_box.bbox[2], y2_t],
                        [current_x1, y2_t],
                    ],
                    confidence=text_box.confidence
                ))

            # Append all split parts to the result
            result_boxes.extend(text_segments)

        # Step 4: Add inline boxes that replaced fully covered text boxes
        for inline_box, assigned_text in inline_assignments.items():
            if assigned_text is None:  # Covers a text box
                result_boxes.append(TextBox(
                    polygon=inline_box.polygon,
                    confidence=inline_box.confidence,
                    math=True
                ))

        return result_boxes