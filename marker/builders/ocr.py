from typing import List

from ftfy import fix_text
from surya.model.detection.model import EfficientViTForSemanticSegmentation
from surya.model.recognition.encoderdecoder import OCREncoderDecoderModel
from surya.ocr import run_ocr

from marker.builders import BaseBuilder
from marker.providers import ProviderOutput, ProviderPageLines
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.polygon import PolygonBox
from marker.schema.registry import get_block_class
from marker.schema.text.line import Line
from marker.schema.text.span import Span
from marker.settings import settings


class OcrBuilder(BaseBuilder):
    """
    A builder for performing OCR on PDF pages and merging the results into the document.

    Attributes:
        detection_batch_size (int):
            The batch size to use for the detection model.
            Default is None, which will use the default batch size for the model.

        recognition_batch_size (int):
            The batch size to use for the recognition model.
            Default is None, which will use the default batch size for the model.

        languages (List[str]):
            A list of languages to use for OCR. Default is None.
    """
    recognition_batch_size: int | None = None
    detection_batch_size: int | None = None
    languages: List[str] | None = None

    def __init__(self, detection_model: EfficientViTForSemanticSegmentation, recognition_model: OCREncoderDecoderModel, config=None):
        super().__init__(config)

        self.detection_model = detection_model
        self.recognition_model = recognition_model

    def __call__(self, document: Document, provider: PdfProvider):
        page_lines = self.ocr_extraction(document, provider)
        self.merge_blocks(document, page_lines)

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

    def ocr_extraction(self, document: Document, provider: PdfProvider) -> ProviderPageLines:
        page_list = [page for page in document.pages if page.text_extraction_method == "surya"]
        recognition_results = run_ocr(
            images=[page.lowres_image for page in page_list],
            langs=[self.languages] * len(page_list),
            det_model=self.detection_model,
            det_processor=self.detection_model.processor,
            rec_model=self.recognition_model,
            rec_processor=self.recognition_model.processor,
            detection_batch_size=int(self.get_detection_batch_size()),
            recognition_batch_size=int(self.get_recognition_batch_size()),
            highres_images=[page.highres_image for page in page_list]
        )

        page_lines = {}

        SpanClass: Span = get_block_class(BlockTypes.Span)
        LineClass: Line = get_block_class(BlockTypes.Line)

        for page_id, recognition_result in zip((page.page_id for page in page_list), recognition_results):
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

    def merge_blocks(self, document: Document, page_lines: ProviderPageLines):
        ocred_pages = [page for page in document.pages if page.text_extraction_method == "surya"]
        for document_page in ocred_pages:
            lines = page_lines[document_page.page_id]
            document_page.merge_blocks(lines, text_extraction_method="surya")
