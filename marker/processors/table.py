import re
from collections import defaultdict
from copy import deepcopy
from typing import Annotated, List

from ftfy import fix_text
from surya.detection import DetectionPredictor
from surya.recognition import RecognitionPredictor, OCRResult
from surya.table_rec import TableRecPredictor
from surya.table_rec.schema import TableResult, TableCell as SuryaTableCell
from pdftext.extraction import table_output

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.blocks.tablecell import TableCell
from marker.schema.document import Document
from marker.schema.polygon import PolygonBox
from marker.settings import settings
from marker.util import matrix_intersection_area


class TableProcessor(BaseProcessor):
    """
    A processor for recognizing tables in the document.
    """
    block_types = (BlockTypes.Table, BlockTypes.TableOfContents, BlockTypes.Form)
    detect_boxes: Annotated[
        bool,
        "Whether to detect boxes for the table recognition model.",
    ] = False
    detector_batch_size: Annotated[
        int,
        "The batch size to use for the table detection model.",
        "Default is None, which will use the default batch size for the model."
    ] = None
    table_rec_batch_size: Annotated[
        int,
        "The batch size to use for the table recognition model.",
        "Default is None, which will use the default batch size for the model."
    ] = None
    recognition_batch_size: Annotated[
        int,
        "The batch size to use for the table recognition model.",
        "Default is None, which will use the default batch size for the model."
    ] = None

    def __init__(
        self,
        detection_model: DetectionPredictor,
        recognition_model: RecognitionPredictor,
        table_rec_model: TableRecPredictor,
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
                image = block.get_image(document, highres=True, expansion=(.01, .01))
                image_poly = block.polygon.rescale((page.polygon.width, page.polygon.height), page.get_image(highres=True).size)

                table_data.append({
                    "block_id": block.id,
                    "page_id": page.page_id,
                    "table_image": image,
                    "table_bbox": image_poly.bbox,
                    "img_size": page.get_image(highres=True).size,
                    "ocr_block": page.text_extraction_method == "surya",
                })

        extract_blocks = [t for t in table_data if not t["ocr_block"]]
        self.assign_pdftext_lines(extract_blocks, filepath) # Handle tables where good text exists in the PDF

        ocr_blocks = [t for t in table_data if t["ocr_block"]]
        self.assign_ocr_lines(ocr_blocks)  # Handle tables where OCR is needed
        assert all("table_text_lines" in t for t in table_data), "All table data must have table cells"

        tables: List[TableResult] = self.table_rec_model(
            [t["table_image"] for t in table_data],
            batch_size=self.get_table_rec_batch_size()
        )
        self.assign_text_to_cells(tables, table_data)
        self.split_combined_rows(tables) # Split up rows that were combined

        # Assign table cells to the table
        table_idx = 0
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                block.structure = [] # Remove any existing lines, spans, etc.
                cells: List[SuryaTableCell] = tables[table_idx].cells
                for cell in cells:
                    # Rescale the cell polygon to the page size
                    cell_polygon = PolygonBox(polygon=cell.polygon).rescale(page.get_image(highres=True).size, page.polygon.size)
                    cell_block = TableCell(
                        polygon=cell_polygon,
                        text="\n".join([self.normalize_spaces(fix_text(t["text"])) for t in cell.text_lines]) if cell.text_lines else "", # Cells can be blank (no text)
                        rowspan=cell.rowspan,
                        colspan=cell.colspan,
                        row_id=cell.row_id,
                        col_id=cell.col_id,
                        is_header=cell.is_header,
                        page_id=page.page_id,
                    )
                    page.add_full_block(cell_block)
                    block.add_structure(cell_block)
                table_idx += 1

    @staticmethod
    def normalize_spaces(text):
        space_chars = [
            '\u2003',  # em space
            '\u2002',  # en space
            '\u00A0',  # non-breaking space
            '\u200B',  # zero-width space
            '\u3000',  # ideographic space
        ]
        for space in space_chars:
            text = text.replace(space, ' ')
        return text

    def split_combined_rows(self, tables: List[TableResult]):
        for table in tables:
            unique_rows = sorted(list(set([c.row_id for c in table.cells])))
            new_cells = []
            shift_up = 0
            max_cell_id = max([c.cell_id for c in table.cells])
            new_cell_count = 0
            for row in unique_rows:
                # Cells in this row
                # Deepcopy is because we do an in-place mutation later, and that can cause rows to shift to match rows in unique_rows
                # making them be processed twice
                row_cells = deepcopy([c for c in table.cells if c.row_id == row and c.cell_id])
                rowspans = [c.rowspan for c in row_cells]
                line_lens = [len(c.text_lines) if isinstance(c.text_lines, list) else 1 for c in row_cells]

                # Other cells that span into this row
                rowspan_cells = [c for c in table.cells if c.row_id != row and c.row_id + c.rowspan > row > c.row_id]
                should_split = all([
                    len(row_cells) > 0,
                    len(rowspan_cells) == 0,
                    all([r == 1 for r in rowspans]),
                    all([l > 1 for l in line_lens]),
                    all([l == line_lens[0] for l in line_lens])
                ])
                if should_split:
                    for i in range(0, line_lens[0]):
                        for cell in row_cells:
                            line = cell.text_lines[i]
                            cell_id = max_cell_id + new_cell_count
                            new_cells.append(
                                SuryaTableCell(
                                    polygon=line["bbox"],
                                    text_lines=[line],
                                    rowspan=1,
                                    colspan=cell.colspan,
                                    row_id=cell.row_id + shift_up + i,
                                    col_id=cell.col_id,
                                    is_header=cell.is_header,
                                    within_row_id=cell.within_row_id,
                                    cell_id=cell_id
                                )
                            )
                            new_cell_count += 1

                    # For each new row we add, shift up subsequent rows
                    shift_up += line_lens[0] - 1
                else:
                    for cell in row_cells:
                        cell.row_id += shift_up
                        new_cells.append(cell)
            table.cells = new_cells

    def assign_text_to_cells(self, tables: List[TableResult], table_data: list):
        for table_result, table_page_data in zip(tables, table_data):
            table_text_lines = table_page_data["table_text_lines"]
            table_cells: List[SuryaTableCell] = table_result.cells
            text_line_bboxes = [t["bbox"] for t in table_text_lines]
            table_cell_bboxes = [c.bbox for c in table_cells]

            intersection_matrix = matrix_intersection_area(text_line_bboxes, table_cell_bboxes)

            cell_text = defaultdict(list)
            for text_line_idx, table_text_line in enumerate(table_text_lines):
                intersections = intersection_matrix[text_line_idx]
                if intersections.sum() == 0:
                    continue

                table_text_line["text"] = fix_text(table_text_line["text"])
                max_intersection = intersections.argmax()
                if not table_cells[max_intersection].text_lines:
                    table_cells[max_intersection].text_lines = []

                cell_text[max_intersection].append(table_text_line)

            for k in cell_text:
                # TODO: see if the text needs to be sorted (based on rotation)
                text = cell_text[k]
                for item in text:
                    item["text"] = re.sub(r"(\s\.){3,}", "...", item["text"]) # Replace . . .
                    item["text"] = re.sub(r"\.{3,}", "...", item["text"]) # Replace ..., like in table of contents

                assert all("text" in t for t in text), "All text lines must have text"
                assert all("bbox" in t for t in text), "All text lines must have a bbox"
                table_cells[k].text_lines = text

    def assign_pdftext_lines(self, extract_blocks: list, filepath: str):
        table_inputs = []
        unique_pages = list(set([t["page_id"] for t in extract_blocks]))
        if len(unique_pages) == 0:
            return

        for page in unique_pages:
            tables = []
            img_size = None
            for block in extract_blocks:
                if block["page_id"] == page:
                    tables.append(block["table_bbox"])
                    img_size = block["img_size"]

            table_inputs.append({
                "tables": tables,
                "img_size": img_size
            })
        cell_text = table_output(filepath, table_inputs, page_range=unique_pages)
        assert len(cell_text) == len(unique_pages), "Number of pages and table inputs must match"

        for pidx, (page_tables, pnum) in enumerate(zip(cell_text, unique_pages)):
            table_idx = 0
            for block in extract_blocks:
                if block["page_id"] == pnum:
                    block["table_text_lines"] = page_tables[table_idx]
                    table_idx += 1
            assert table_idx == len(page_tables), "Number of tables and table inputs must match"

    def assign_ocr_lines(self, ocr_blocks: list):
        det_images = [t["table_image"] for t in ocr_blocks]
        ocr_results: List[OCRResult] = self.recognition_model(
            det_images,
            [None] * len(det_images),
            self.detection_model,
            recognition_batch_size=self.get_recognition_batch_size(),
            detection_batch_size=self.get_detector_batch_size()
        )

        for block, ocr_res in zip(ocr_blocks, ocr_results):
            table_cells = []
            for line in ocr_res.text_lines:
                # Don't need to correct back to image size
                # Table rec boxes are relative to the table
                table_cells.append({
                    "bbox": line.bbox,
                    "text": line.text
                })
            block["table_text_lines"] = table_cells


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
