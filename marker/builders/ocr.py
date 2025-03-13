import copy
from typing import Annotated, List, Optional
import re

from ftfy import fix_text
from surya.recognition import RecognitionPredictor, OCRResult, TextChar

from marker.builders import BaseBuilder
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.blocks import BlockId
from marker.schema.document import Document
from marker.schema.groups import PageGroup
from marker.schema.registry import get_block_class
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
        "Default is None, which will use the default batch size for the model."
    ] = None
    languages: Annotated[
        Optional[List[str]],
        "A list of languages to use for OCR.",
        "Default is None."
    ] = None
    disable_tqdm: Annotated[
        bool,
        "Disable tqdm progress bars.",
    ] = False

    def __init__(self, recognition_model: RecognitionPredictor, config=None):
        super().__init__(config)

        self.recognition_model = recognition_model

    def __call__(self, document: Document, provider: PdfProvider):
        pages_to_ocr = [page for page in document.pages if page.text_extraction_method == 'surya']
        images, line_boxes, line_ids = self.get_ocr_images_boxes_ids(document, pages_to_ocr, provider)
        self.ocr_extraction(document, pages_to_ocr, provider, images, line_boxes, line_ids)

    def get_recognition_batch_size(self):
        if self.recognition_batch_size is not None:
            return self.recognition_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 32
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 32
        return 32

    def get_ocr_images_boxes_ids(self, document: Document, pages: List[PageGroup], provider: PdfProvider):
        highres_images, highres_boxes, line_ids = [], [], []
        for document_page in pages:
            page_highres_image = document_page.get_image(highres=True)
            page_highres_boxes = []
            page_line_ids = []

            page_size = provider.get_page_bbox(document_page.page_id).size
            image_size = page_highres_image.size
            for block in document_page.contained_blocks(document):
                block_lines = block.contained_blocks(document, [BlockTypes.Line])
                block_detected_lines = [block_line for block_line in block_lines if block_line.text_extraction_method == 'surya']
                
                block.text_extraction_method = 'surya'
                for line in block_detected_lines:
                    line_polygon = copy.deepcopy(line.polygon)
                    page_highres_boxes.append(line_polygon.rescale(page_size, image_size).bbox)
                    page_line_ids.append(line.id)

            highres_images.append(page_highres_image)
            highres_boxes.append(page_highres_boxes)
            line_ids.append(page_line_ids)

        return highres_images, highres_boxes, line_ids

    def ocr_extraction(self, document: Document, pages: List[PageGroup], provider: PdfProvider, images: List[any], line_boxes: List[List[float]], line_ids: List[List[BlockId]]):
        if sum(len(b) for b in line_boxes)==0:
            return

        self.recognition_model.disable_tqdm = self.disable_tqdm
        recognition_results: OCRResult = self.recognition_model(
            images=images,
            task_names=['ocr_with_boxes'] * len(images),
            bboxes=line_boxes,
            recognition_batch_size=int(self.get_recognition_batch_size()),
            sort_lines=False
        )

        for document_page, page_recognition_result, page_line_ids in zip(pages, recognition_results, line_ids):
            for line_id, ocr_line in zip(page_line_ids, page_recognition_result.text_lines):
                if not fix_text(ocr_line.text):
                    continue
                new_spans = self.spans_from_html_chars(ocr_line.chars, document_page.page_id)

                line = document_page.get_block(line_id)
                assert line.structure is None
                for span in new_spans:
                    document_page.add_full_block(span)
                    line.add_structure(span)

    def spans_from_html_chars(self, chars: List[TextChar], page_id: int):
        SpanClass: Span = get_block_class(BlockTypes.Span)
        spans = []
        formats = {'plain'}

        current_span = None
        for char in chars:
            is_opening_tag, format = get_opening_tag_type(char.text)
            if is_opening_tag and format not in formats:
                formats.add(format)
                if current_span:
                    spans.append(current_span)
                    current_span = None
                if format == 'math':
                    current_span = SpanClass(
                        text='',
                        formats=list(formats),
                        page_id=page_id,
                        polygon=PolygonBox(polygon=char.polygon),
                        minimum_position=0,
                        maximum_position=0,
                        font='Unknown',
                        font_weight=0,
                        font_size=0,
                    ) 
                continue

            is_closing_tag, format = get_closing_tag_type(char.text)
            if is_closing_tag:
                formats.remove(format)
                if current_span and format=='math':
                    if format == 'math':
                        current_span.html = f'<math display="inline">{current_span.text}</math>'
                    spans.append(current_span)
                    current_span = None
                continue

            if not current_span:
                current_span = SpanClass(
                    text=char.text,
                    formats=list(formats),
                    page_id=page_id,
                    polygon=PolygonBox(polygon=char.polygon),
                    minimum_position=0,
                    maximum_position=0,
                    font='Unknown',
                    font_weight=0,
                    font_size=0,
                )
                continue
            

            current_span.text += char.text
            # Tokens inside a math span don't have valid boxes, so we skip the merging
            if 'math' not in formats:
                current_span.polygon = current_span.polygon.merge([PolygonBox(polygon=char.polygon)])
            
        # Add the last span to the list
        if current_span:
            spans.append(current_span)

        # Add newline after all spans finish
        if not spans[-1].html:
            spans[-1].text += '\n'

        return spans