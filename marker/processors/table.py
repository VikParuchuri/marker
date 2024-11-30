
from ftfy import fix_text
from surya.input.pdflines import get_page_text_lines
from surya.model.detection.model import EfficientViTForSemanticSegmentation
from surya.model.recognition.encoderdecoder import OCREncoderDecoderModel
from surya.model.table_rec.encoderdecoder import TableRecEncoderDecoderModel
from tabled.assignment import assign_rows_columns
from tabled.inference.recognition import get_cells, recognize_tables

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.settings import settings


class TableProcessor(BaseProcessor):
    """
    A processor for recognizing tables in the document.

    Attributes:
        detect_boxes (bool):
            Whether to detect boxes for the table recognition model.
            Default is False.

        detector_batch_size (int):
            The batch size to use for the table detection model.
            Default is None, which will use the default batch size for the model.

        table_rec_batch_size (int):
            The batch size to use for the table recognition model.
            Default is None, which will use the default batch size for the model.

        recognition_batch_size (int):
            The batch size to use for the table recognition model.
            Default is None, which will use the default batch size for the model.
    """
    block_types = (BlockTypes.Table, BlockTypes.TableOfContents, BlockTypes.Form)
    detect_boxes = False
    detector_batch_size = None
    table_rec_batch_size = None
    recognition_batch_size = None

    def __init__(
        self,
        detection_model: EfficientViTForSemanticSegmentation,
        recognition_model: OCREncoderDecoderModel,
        table_rec_model: TableRecEncoderDecoderModel,
        config=None
    ):
        super().__init__(config)

        self.detection_model = detection_model
        self.recognition_model = recognition_model
        self.table_rec_model = table_rec_model

    def __call__(self, document: Document):
        filepath = document.filepath  # Path to original pdf file

        table_data = []
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                image_poly = block.polygon.rescale((page.polygon.width, page.polygon.height), page.highres_image.size)
                image = page.highres_image.crop(image_poly.bbox).convert("RGB")

                if block.text_extraction_method == "surya":
                    text_lines = None
                else:
                    text_lines = get_page_text_lines(
                        filepath,
                        [page.page_id],
                        [page.highres_image.size],
                        flatten_pdf=True
                    )[0]

                table_data.append({
                    "block_id": block.id,
                    "table_image": image,
                    "table_bbox": image_poly.bbox,
                    "text_lines": text_lines,
                    "img_size": page.highres_image.size
                })

        lst_format = [[t[key] for t in table_data] for key in ["table_image", "table_bbox", "img_size", "text_lines"]]

        cells, needs_ocr = get_cells(
            *lst_format,
            [self.detection_model, self.detection_model.processor],
            detect_boxes=self.detect_boxes,
            detector_batch_size=self.get_detector_batch_size()
        )

        tables = recognize_tables(
            [t["table_image"] for t in table_data],
            cells,
            needs_ocr,
            [self.table_rec_model, self.table_rec_model.processor, self.recognition_model, self.recognition_model.processor],
            table_rec_batch_size=self.get_table_rec_batch_size(),
            ocr_batch_size=self.get_recognition_batch_size()
        )

        for table_d, table_res in zip(table_data, tables):
            block = document.get_block(table_d["block_id"])
            cells = assign_rows_columns(table_res, table_d["img_size"])
            for cell in cells:
                cell.text = fix_text(cell.text)
            block.cells = cells

    def get_detector_batch_size(self):
        if self.detector_batch_size is not None:
            return self.detector_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 4
        return 4

    def get_table_rec_batch_size(self):
        if self.table_rec_batch_size is not None:
            return self.table_rec_batch_size
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 6
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 6
        return 6

    def get_recognition_batch_size(self):
        if self.recognition_batch_size is not None:
            return self.recognition_batch_size
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 32
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 32
        return 32
