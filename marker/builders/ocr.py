from typing import Annotated, List, Optional, Tuple

from ftfy import fix_text
import numpy as np
from surya.detection import DetectionPredictor
from surya.recognition import RecognitionPredictor
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
from marker.util import matrix_intersection_area, rescale_bbox


class OcrBuilder(BaseBuilder):
    """
    A builder for performing OCR on PDF pages and merging the results into the document.
    """
    recognition_batch_size: Annotated[
        Optional[int],
        "The batch size to use for the recognition model.",
        "Default is None, which will use the default batch size for the model."
    ] = None
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
    languages: Annotated[
        Optional[List[str]],
        "A list of languages to use for OCR.",
        "Default is None."
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
    ] = .1
    document_ocr_threshold: Annotated[
        float,
        "The minimum ratio of pages that must pass the layout coverage check",
        "to avoid OCR.",
    ] = .8
    excluded_for_coverage: Annotated[
        Tuple[BlockTypes],
        "A list of block types to exclude from the layout coverage check.",
    ] = (BlockTypes.Figure, BlockTypes.Picture, BlockTypes.Table, BlockTypes.FigureGroup, BlockTypes.TableGroup, BlockTypes.PictureGroup)

    def __init__(self, detection_model: DetectionPredictor, recognition_model: RecognitionPredictor, ocr_error_model: OCRErrorPredictor, config=None):
        super().__init__(config)

        self.detection_model = detection_model
        self.recognition_model = recognition_model
        self.ocr_error_model = ocr_error_model

    def __call__(self, document: Document, provider: PdfProvider):
        provider_lines, ocr_lines= self.get_all_lines(document, provider)
        self.merge_blocks(document, provider_lines, ocr_lines)

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

    def get_ocr_error_batch_size(self):
        if self.ocr_error_batch_size is not None:
            return self.ocr_error_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 4
        return 4

    def get_all_lines(self, document: Document, provider: PdfProvider):
        detection_results = self.detection_model(
            images=[page.get_image(highres=False, remove_tables=not self.enable_table_ocr) for page in document.pages],
            detect_inline_math=True
        )
        ocr_error_detection_results = self.ocr_error_detection(document.pages, provider.page_lines)

        #For each page, need to carry out the following steps:
        lines_to_ocr = {page.page_id: [] for page in document.pages}
        page_lines = {page.page_id: [] for page in document.pages}

        SpanClass: Span = get_block_class(BlockTypes.Span)
        LineClass: Line = get_block_class(BlockTypes.Line)

        for document_page, detection_result, ocr_error_detection_label in zip(document.pages, detection_results, ocr_error_detection_results.labels):
            provider_lines = provider.page_lines.get(document_page.page_id, [])
            detected_text_lines = [box for box in detection_result.bboxes if not box.math]
            detected_inline_math_lines = [box for box in detection_result.bboxes if box.math]
            image_size = PolygonBox.from_bbox(detection_result.image_bbox).size
            page_size = provider.get_page_bbox(document_page.page_id).size

            provider_lines_good = bool(provider) and ocr_error_detection_label!='bad' and self.check_layout_coverage(document_page, provider_lines)

            if provider_lines_good:
                #Merge inline math blocks into the provider lines, only persist new detected text lines which do not overlap with existing provider lines
                page_lines[document_page.page_id].extend(self.merge_provider_lines_inline_math(document_page.page_id, provider_lines, detected_inline_math_lines, image_size, page_size))
                continue

            #Skip inline math merging if no provider lines are good; OCR all text lines and all inline math lines
            lines_to_ocr[document_page.page_id].extend(detected_text_lines)
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

        ocr_lines = self.ocr_extraction(document, provider, lowres_detected_text_lines=lines_to_ocr)

        return page_lines, ocr_lines


    def filter_detected_text_lines(self, provider_lines, detected_text_lines, image_size, page_size, threshold=0.8):
        filtered_lines = []
        for detected_line in detected_text_lines:
            keep_line = True
            detected_line_polygon = PolygonBox(polygon=detected_line.polygon).rescale(image_size, page_size)
            detected_line_area = detected_line_polygon.area
            for provider_line in provider_lines:
                intersection_area = provider_line.line.polygon.intersection_area(detected_line_polygon)
                if detected_line_area > 0 and (intersection_area / detected_line_area) > threshold:
                    keep_line = False
                    break
            
            if keep_line:
                filtered_lines.append(detected_line)
        
        return filtered_lines


    def merge_provider_lines_inline_math(self, document_page_id, provider_lines, inline_math_lines, image_size, page_size, min_inline_overlap=0.1, span_overlap_threshold=0.4):
        updated_provider_lines = []
        provider_to_math = {provider_line: [] for provider_line in provider_lines}

        SpanClass: Span = get_block_class(BlockTypes.Span)

        for math_line in inline_math_lines:
            math_line_polygon = PolygonBox(polygon=math_line.polygon).rescale(image_size, page_size)
            math_line_area = math_line_polygon.area
            best_match = None
            best_overlap = min_inline_overlap if min_inline_overlap else 0        #Start with this threshold atleast, skip all boxes if not reached

            for provider_line in provider_lines:
                intersection_area = provider_line.line.polygon.intersection_area(math_line_polygon)
                
                if math_line_area > 0:
                    overlap = intersection_area / math_line_area
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_match = provider_line
            
            if best_match:
                provider_to_math[best_match].append(math_line)

        for provider_line, math_lines in provider_to_math.items():
            #No intersection with math, or vertical text line - Skip
            if not math_lines or provider_line.line.polygon.height>provider_line.line.polygon.width:
                updated_provider_lines.append(provider_line)
                continue

            #Remove all spans in the line that intersect with the math line
            spans_to_keep = []
            for span in provider_line.spans:
                flag = False
                span_area = span.polygon.area
                if span_area==0:
                    print(f'Zero area {span}')
                for math_line in math_lines:
                    math_line_polygon = PolygonBox(polygon=math_line.polygon).rescale(image_size, page_size)
                    overlap = span.polygon.intersection_area(math_line_polygon)/span_area
                    if overlap>span_overlap_threshold:
                        flag = True
                        break
                if not flag:
                    spans_to_keep.append(span)



            #Add math lines in as new spans. 
            for math_line in math_lines:
                spans_to_keep.append(
                    SpanClass(
                        text="INLINE",
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
            provider_line.spans = sorted(spans_to_keep, key=lambda s:s.polygon.x_start)
            updated_provider_lines.append(provider_line)

        return updated_provider_lines

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


    def ocr_extraction(self, document: Document, provider: PdfProvider, lowres_detected_text_lines:any) -> ProviderPageLines:
        highres_images, scaled_bboxes = [], []
        for document_page in document.pages:
            highres_image = document_page.get_image(highres=True, remove_tables=not self.enable_table_ocr)
            highres_size = highres_image.size

            lowres_size = document_page.get_image(highres=False).size

            lowres_boxes = [line.bbox for line in lowres_detected_text_lines[document_page.page_id]]
            highres_boxes = list(map(rescale_bbox, lowres_boxes, [lowres_size]*len(lowres_boxes), [highres_size]*len(lowres_boxes)))

            highres_images.append(highres_image)
            scaled_bboxes.append(highres_boxes)

        if sum(len(b) for b in scaled_bboxes)==0:
            print('Should be hitting this a lot')
            return {page.page_id: [] for page in document.pages}

        # Remove tables because we re-OCR them later with the table processor
        recognition_results = self.recognition_model(
            images=highres_images,
            bboxes=scaled_bboxes,
            langs=[self.languages] * len(document.pages),
            recognition_batch_size=int(self.get_recognition_batch_size()),
        )

        page_lines = {}

        SpanClass: Span = get_block_class(BlockTypes.Span)
        LineClass: Line = get_block_class(BlockTypes.Line)

        for page_id, recognition_result in zip((page.page_id for page in document.pages), recognition_results):
            page_lines.setdefault(page_id, [])

            page_size = provider.get_page_bbox(page_id).size

            for ocr_line_idx, ocr_line in enumerate(recognition_result.text_lines):
                image_polygon = PolygonBox.from_bbox(recognition_result.image_bbox)
                polygon = PolygonBox.from_bbox(ocr_line.bbox).rescale(image_polygon.size, page_size)

                line = LineClass(
                    polygon=polygon,
                    page_id=page_id,
                )
                spans = [
                    SpanClass(
                        text=fix_text(ocr_line.text) + "\n",
                        formats=['plain'],
                        page_id=page_id,
                        polygon=polygon,
                        minimum_position=0,
                        maximum_position=0,
                        font='Unknown',
                        font_weight=0,
                        font_size=0,
                    )
                ]

                page_lines[page_id].append(ProviderOutput(line=line, spans=spans))

        return page_lines

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
        for document_page in document.pages:
            document_page.merge_blocks(page_provider_lines[document_page.page_id], text_extraction_method="pdftext")
            document_page.merge_blocks(page_ocr_lines[document_page.page_id], text_extraction_method="surya")