import copy
from typing import Annotated, List, Optional

from ftfy import fix_text
from surya.common.surya.schema import TaskNames
from surya.recognition import RecognitionPredictor, OCRResult, TextChar

from marker.builders import BaseBuilder
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.blocks import BlockId
from marker.schema.document import Document
from marker.schema.groups import PageGroup
from marker.schema.registry import get_block_class
from marker.schema.text.line import Line
from marker.schema.text.span import Span
from marker.settings import settings
from marker.schema.polygon import PolygonBox
from marker.util import get_opening_tag_type, get_closing_tag_type


class OcrBuilder(BaseBuilder):
    """
    A builder for performing OCR on PDF pages and merging the results into the document.
    """

    recognition_batch_size: Annotated[
        Optional[int],
        "The batch size to use for the recognition model.",
        "Default is None, which will use the default batch size for the model.",
    ] = None
    disable_tqdm: Annotated[
        bool,
        "Disable tqdm progress bars.",
    ] = False
    skip_ocr_blocks: Annotated[
        List[BlockTypes],
        "Blocktypes for which contained lines are not processed by the OCR model"
        "By default, this avoids recognizing lines inside equations",
    ] = BlockTypes.Equation
    ocr_task_name: Annotated[
        str,
        "The OCR mode to use, see surya for details.  Set to 'ocr_without_boxes' for potentially better performance, at the expense of formatting.",
    ] = TaskNames.ocr_with_boxes
    disable_ocr_math: Annotated[bool, "Disable inline math recognition in OCR"] = False

    def __init__(self, recognition_model: RecognitionPredictor, config=None):
        super().__init__(config)

        self.recognition_model = recognition_model

    def __call__(self, document: Document, provider: PdfProvider):
        # pages_to_ocr = [page for page in document.pages if page.text_extraction_method == 'surya']
        pages_to_ocr = [page for page in document.pages]
        images, line_boxes, line_ids, line_original_texts = (
            self.get_ocr_images_boxes_ids(document, pages_to_ocr, provider)
        )
        self.ocr_extraction(
            document,
            pages_to_ocr,
            provider,
            images,
            line_boxes,
            line_ids,
            line_original_texts,
        )

    def get_recognition_batch_size(self):
        if self.recognition_batch_size is not None:
            return self.recognition_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 64
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 32
        return 32

    def get_ocr_images_boxes_ids(
        self, document: Document, pages: List[PageGroup], provider: PdfProvider
    ):
        highres_images, highres_boxes, line_ids, line_original_texts = [], [], [], []
        for document_page in pages:
            page_highres_image = document_page.get_image(highres=True)
            page_highres_boxes = []
            page_line_ids = []
            page_line_original_texts = []

            page_size = provider.get_page_bbox(document_page.page_id).size
            image_size = page_highres_image.size
            # Search by block, and the lines, so that we can filter based on containing block type
            for block in document_page.contained_blocks(document):
                if block.block_type in self.skip_ocr_blocks:
                    continue
                block_lines = block.contained_blocks(document, [BlockTypes.Line])
                block_lines_to_ocr = [
                    block_line
                    for block_line in block_lines
                    if block_line.text_extraction_method == "surya"
                ]

                # Set extraction method of OCR-only pages
                if document_page.text_extraction_method == "surya":
                    block.text_extraction_method = "surya"

                for line in block_lines_to_ocr:
                    # Fit the polygon to image bounds since PIL image crop expands by default which might create bad images for the OCR model.
                    line_polygon_rescaled = copy.deepcopy(line.polygon).rescale(page_size, image_size).fit_to_bounds((0, 0, *image_size))
                    line_bbox_rescaled = line_polygon_rescaled.bbox

                    page_highres_boxes.append(
                        line_bbox_rescaled
                    )
                    page_line_ids.append(line.id)
                    # For OCRed pages, this text will be blank
                    page_line_original_texts.append(
                        line.formatted_text(document, skip_urls=True).rstrip()
                    )

            highres_images.append(page_highres_image)
            highres_boxes.append(page_highres_boxes)
            line_ids.append(page_line_ids)
            line_original_texts.append(page_line_original_texts)

        return highres_images, highres_boxes, line_ids, line_original_texts

    def ocr_extraction(
        self,
        document: Document,
        pages: List[PageGroup],
        provider: PdfProvider,
        images: List[any],
        line_boxes: List[List[List[float]]],
        line_ids: List[List[BlockId]],
        line_original_texts: List[List[str]],
    ):
        if sum(len(b) for b in line_boxes) == 0:
            return

        self.recognition_model.disable_tqdm = self.disable_tqdm
        recognition_results: OCRResult = self.recognition_model(
            images=images,
            task_names=[self.ocr_task_name] * len(images),
            bboxes=line_boxes,
            input_text=line_original_texts,
            recognition_batch_size=int(self.get_recognition_batch_size()),
            sort_lines=False,
            math_mode=not self.disable_ocr_math,
        )

        for document_page, page_recognition_result, page_line_ids in zip(
            pages, recognition_results, line_ids
        ):
            for line_id, ocr_line in zip(
                page_line_ids, page_recognition_result.text_lines
            ):
                if ocr_line.original_text_good:
                    continue
                if not fix_text(ocr_line.text):
                    continue
                new_spans = self.spans_from_html_chars(
                    ocr_line.chars, document_page.page_id
                )

                line = document_page.get_block(line_id)
                self.replace_line_spans(document, document_page, line, new_spans)

    # TODO Fix polygons when we cut the span into multiple spans
    def link_and_break_span(self, span: Span, text: str, match_text, url: str):
        before_text, _, after_text = text.partition(match_text)
        before_span, after_span = None, None
        if before_text:
            before_span = copy.deepcopy(span)
            before_span.text = before_text
        if after_text:
            after_span = copy.deepcopy(span)
            after_span.text = after_text

        match_span = copy.deepcopy(span)
        match_span.text = match_text
        match_span.url = url

        return before_span, match_span, after_span

    # Pull all refs from old spans and attempt to insert back into appropriate place in new spans
    def replace_line_spans(
        self, document: Document, page: PageGroup, line: Line, new_spans: List[Span]
    ):
        old_spans = line.contained_blocks(document, [BlockTypes.Span])
        text_ref_matching = {span.text: span.url for span in old_spans if span.url}

        # Insert refs into new spans, since the OCR model does not (cannot) generate these
        final_new_spans = []
        for span in new_spans:
            # Use for copying attributes into new spans
            original_span = copy.deepcopy(span)
            remaining_text = span.text
            while remaining_text:
                matched = False
                for match_text, url in text_ref_matching.items():
                    if match_text in remaining_text:
                        matched = True
                        before, current, after = self.link_and_break_span(
                            original_span, remaining_text, match_text, url
                        )
                        if before:
                            final_new_spans.append(before)
                        final_new_spans.append(current)
                        if after:
                            remaining_text = after.text
                        # Prevent repeat matches
                        del text_ref_matching[match_text]
                        break
                if not matched:
                    remaining_span = copy.deepcopy(original_span)
                    remaining_span.text = remaining_text
                    final_new_spans.append(remaining_span)
                    break

        # Clear the old spans from the line
        line.structure = []
        for span in final_new_spans:
            page.add_full_block(span)
            line.structure.append(span)

    def spans_from_html_chars(self, chars: List[TextChar], page_id: int):
        SpanClass: Span = get_block_class(BlockTypes.Span)
        spans = []
        formats = {"plain"}

        current_span = None
        for char in chars:
            is_opening_tag, format = get_opening_tag_type(char.text)
            if is_opening_tag and format not in formats:
                formats.add(format)
                if current_span:
                    spans.append(current_span)
                    current_span = None
                if format == "math":
                    current_span = SpanClass(
                        text="",
                        formats=list(formats),
                        page_id=page_id,
                        polygon=PolygonBox(polygon=char.polygon),
                        minimum_position=0,
                        maximum_position=0,
                        font="Unknown",
                        font_weight=0,
                        font_size=0,
                    )
                continue

            is_closing_tag, format = get_closing_tag_type(char.text)
            if is_closing_tag:
                # Useful since the OCR model sometimes returns closing tags without an opening tag
                try:
                    formats.remove(format)
                except Exception:
                    continue
                if current_span:
                    if format == "math":
                        current_span.html = (
                            f'<math display="inline">{current_span.text}</math>'
                        )
                    spans.append(current_span)
                    current_span = None
                continue

            if not current_span:
                current_span = SpanClass(
                    text=fix_text(char.text),
                    formats=list(formats),
                    page_id=page_id,
                    polygon=PolygonBox(polygon=char.polygon),
                    minimum_position=0,
                    maximum_position=0,
                    font="Unknown",
                    font_weight=0,
                    font_size=0,
                )
                continue

            current_span.text = fix_text(current_span.text + char.text)
            # Tokens inside a math span don't have valid boxes, so we skip the merging
            if "math" not in formats:
                current_span.polygon = current_span.polygon.merge(
                    [PolygonBox(polygon=char.polygon)]
                )

        # Add the last span to the list
        if current_span:
            spans.append(current_span)

        # Add newline after all spans finish
        if not spans[-1].html:
            spans[-1].text += "\n"

        return spans
