import copy
from typing import Annotated, List, Optional

from ftfy import fix_text
from surya.recognition import RecognitionPredictor

from marker.builders import BaseBuilder
from marker.providers import ProviderPageLines
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.blocks import BlockId
from marker.schema.document import Document
from marker.schema.registry import get_block_class
from marker.schema.text.span import Span
from marker.settings import settings

class OcrBuilder(BaseBuilder):
    """
    A builder for performing OCR on PDF pages and merging the results into the document.
    """
    recognition_batch_size: Annotated[
        Optional[int],
        "The batch size to use for the recognition model.",
        "Default is None, which will use the default batch size for the model."
    ] = None
    enable_table_ocr: Annotated[
        bool,
        "Whether to skip OCR on tables.  The TableProcessor will re-OCR them.  Only enable if the TableProcessor is not running.",
    ] = False
    block_ocr_threshold: Annotated[
        float,
        "The minimum fraction of detected lines in a block to OCR the block"
    ] = 0.
    languages: Annotated[
        Optional[List[str]],
        "A list of languages to use for OCR.",
        "Default is None."
    ] = None

    def __init__(self, recognition_model: RecognitionPredictor, config=None):
        super().__init__(config)

        self.recognition_model = recognition_model

    def __call__(self, document: Document, provider: PdfProvider):
        images, line_boxes, line_ids = self.get_ocr_images_boxes_ids(document, provider)
        self.ocr_extraction(document, provider, images, line_boxes, line_ids)

    def get_recognition_batch_size(self):
        if self.recognition_batch_size is not None:
            return self.recognition_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 32
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 32
        return 32

    def get_ocr_images_boxes_ids(self, document: Document, provider: PdfProvider):
        highres_images, highres_boxes, line_ids = [], [], []
        for document_page in document.pages:
            page_highres_image = document_page.get_image(highres=True, remove_tables=not self.enable_table_ocr)
            page_highres_boxes = []
            page_line_ids = []

            page_size = provider.get_page_bbox(document_page.page_id).size
            image_size = page_highres_image.size
            for block in document_page.contained_blocks(document):
                block_lines = block.contained_blocks(document, [BlockTypes.Line])
                block_detected_lines = [block_line for block_line in block_lines if block_line.text_extraction_method=='surya']
                if len(block_lines)==0 or len(block_detected_lines)/len(block_lines)<self.block_ocr_threshold:
                    continue

                for line in block_detected_lines:
                    line_polygon = copy.deepcopy(line.polygon)
                    page_highres_boxes.append(line_polygon.rescale(page_size, image_size).bbox)
                    page_line_ids.append(line.id)

            highres_images.append(page_highres_image)
            highres_boxes.append(page_highres_boxes)
            line_ids.append(page_line_ids)

        return highres_images, highres_boxes, line_ids

    def ocr_extraction(self, document: Document, provider: PdfProvider, images: List[any], line_boxes: List[List[float]], line_ids: List[List[BlockId]]) -> ProviderPageLines:
        if sum(len(b) for b in line_boxes)==0:
            return

        # Remove tables because we re-OCR them later with the table processor
        recognition_results = self.recognition_model(
            images=images,
            bboxes=line_boxes,
            langs=[self.languages] * len(document.pages),
            recognition_batch_size=int(self.get_recognition_batch_size()),
        )

        SpanClass: Span = get_block_class(BlockTypes.Span)
        for document_page, page_recognition_result, page_line_ids in zip(document.pages, recognition_results, line_ids):
            for line_id, ocr_line in zip(page_line_ids, page_recognition_result.text_lines):
                line = document_page.get_block(line_id)
                assert line.structure is None
                new_span = SpanClass(
                    text=fix_text(ocr_line.text) + '\n',
                    formats=['math'],
                    page_id=document_page.page_id,
                    polygon=copy.deepcopy(line.polygon),
                    minimum_position=0,
                    maximum_position=0,
                    font='Unknown',
                    font_weight=0,
                    font_size=0,
                )
                document_page.add_full_block(new_span)
                line.add_structure(new_span)