from typing import Optional

from pydantic import BaseModel
from surya.input.pdflines import get_page_text_lines
from tabled.assignment import assign_rows_columns
from tabled.inference.recognition import get_cells, recognize_tables

from marker.settings import settings
from marker.v2.processors import BaseProcessor
from marker.v2.schema import BlockTypes
from marker.v2.schema.document import Document


class TableProcessor(BaseProcessor):
    block_type = BlockTypes.Table
    detect_boxes = False
    detector_batch_size = None
    table_rec_batch_size = None
    ocr_batch_size = None

    def __init__(self, detection_model, ocr_model, table_rec_model, config: Optional[BaseModel] = None):
        super().__init__(config)

        self.detection_model = detection_model
        self.ocr_model = ocr_model
        self.table_rec_model = table_rec_model

    def __call__(self, document: Document):
        filepath = document.filepath # Path to original pdf file

        table_data = []
        for page in document.pages:
            for block in page.children:
                if block.block_type != self.block_type:
                    continue

                image_poly = block.polygon.rescale((page.polygon.width, page.polygon.height), page.highres_image.size)
                image = page.highres_image.crop(image_poly.bbox).convert("RGB")

                if block.text_extraction_method == "ocr":
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
            [self.table_rec_model, self.table_rec_model.processor, self.ocr_model, self.ocr_model.processor],
            table_rec_batch_size=self.get_table_rec_batch_size(),
            ocr_batch_size=self.get_ocr_batch_size()
        )

        for table_d, table_res in zip(table_data, tables):
            block = document.get_block(table_d["block_id"])
            cells = assign_rows_columns(table_res, table_d["img_size"])
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
            return 16
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 64
        return 8

    def get_ocr_batch_size(self):
        if self.ocr_batch_size is not None:
            return self.ocr_batch_size
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 32
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 128
        return 32