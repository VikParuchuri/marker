from collections import defaultdict

import pandas as pd
from marker.schema.bbox import merge_boxes, box_intersection_pct, rescale_bbox
from marker.schema.block import Line, Span, Block
from marker.schema.page import Page
from tabulate import tabulate
from typing import List

from marker.settings import settings
from marker.tables.detections import cluster_horizontal_lines, cluster_vertical_lines, detect_borderlines, detect_horizontal_textlines, extend_lines, filter_non_intersecting_lines
from marker.tables.intersections import detect_rowwise_intersection, detect_boxes, get_cells, fill_text_in_cells
from marker.tables.utils import sort_table_blocks, replace_dots, replace_newlines

import fitz
import PIL
import pytesseract
import torch
from marker.tables.schema import Rectangle
import tempfile
from marker.tables.utils import save_table_image
import cv2

def get_table_surya(page, table_box, space_tol=.01) -> List[List[str]]:
    table_rows = []
    table_row = []
    x_position = None
    sorted_blocks = sort_table_blocks(page.blocks)
    for block_idx, block in enumerate(sorted_blocks):
        sorted_lines = sort_table_blocks(block.lines)
        for line_idx, line in enumerate(sorted_lines):
            line_bbox = line.bbox
            intersect_pct = box_intersection_pct(line_bbox, table_box)
            if intersect_pct < .5 or len(line.spans) == 0:
                continue
            normed_x_start = line_bbox[0] / page.width
            normed_x_end = line_bbox[2] / page.width

            cells = [[s.bbox, s.text] for s in line.spans]
            if x_position is None or normed_x_start > x_position - space_tol:
                # Same row
                table_row.extend(cells)
            else:
                # New row
                if len(table_row) > 0:
                    table_rows.append(table_row)
                table_row = cells
            x_position = normed_x_end
    if len(table_row) > 0:
        table_rows.append(table_row)
    table_rows = assign_cells_to_columns(page, table_box, table_rows)
    return table_rows


def get_table_pdftext(page: Page, table_box, space_tol=.01, round_factor=4) -> List[List[str]]:
    page_width = page.width
    table_rows = []
    table_cell = ""
    cell_bbox = None
    table_row = []
    sorted_char_blocks = sort_table_blocks(page.char_blocks)

    table_width = table_box[2] - table_box[0]
    new_line_start_x = table_box[0] + table_width * .2

    for block_idx, block in enumerate(sorted_char_blocks):
        sorted_lines = sort_table_blocks(block["lines"])
        for line_idx, line in enumerate(sorted_lines):
            line_bbox = line["bbox"]
            intersect_pct = box_intersection_pct(line_bbox, table_box)
            if intersect_pct < settings.BBOX_INTERSECTION_THRESH:
                continue
            for span in line["spans"]:
                for char in span["chars"]:
                    x_start, y_start, x_end, y_end = char["bbox"]
                    x_start /= page_width
                    x_end /= page_width

                    if cell_bbox is not None:
                        # Find boundaries of cell bbox before merging
                        cell_x_start, cell_y_start, cell_x_end, cell_y_end = cell_bbox
                        cell_x_start /= page_width
                        cell_x_end /= page_width

                    cell_content = replace_dots(replace_newlines(table_cell))
                    if cell_bbox is None: # First char
                        table_cell += char["char"]
                        cell_bbox = char["bbox"]
                    elif cell_x_start - space_tol < x_start < cell_x_end + space_tol: # Check if we are in the same cell
                        table_cell += char["char"]
                        cell_bbox = merge_boxes(cell_bbox, char["bbox"])
                    # New line and cell
                    # Use x_start < new_line_start_x to account for out-of-order cells in the pdf
                    elif x_start < cell_x_end - space_tol and x_start < new_line_start_x:
                        if len(table_cell) > 0:
                            table_row.append((cell_bbox, cell_content))
                        table_cell = char["char"]
                        cell_bbox = char["bbox"]
                        if len(table_row) > 0:
                            table_row = sorted(table_row, key=lambda x: round(x[0][0] / round_factor))
                            table_rows.append(table_row)
                        table_row = []
                    else: # Same line, new cell, check against cell bbox
                        if len(table_cell) > 0:
                            table_row.append((cell_bbox, cell_content))
                        table_cell = char["char"]
                        cell_bbox = char["bbox"]

    if len(table_cell) > 0:
        table_row.append((cell_bbox, replace_dots(replace_newlines(table_cell))))
    if len(table_row) > 0:
        table_row = sorted(table_row, key=lambda x: round(x[0][0] / round_factor))
        table_rows.append(table_row)

    table_rows = assign_cells_to_columns(page, table_box, table_rows)
    return table_rows


def format_tables(pages: List[Page]):
    # Formats tables nicely into github flavored markdown
    table_count = 0
    for page in pages:
        table_insert_points = {}
        blocks_to_remove = set()
        pnum = page.pnum
        page_table_boxes = [b for b in page.layout.bboxes if b.label == "Table"]
        page_table_boxes = [rescale_bbox(page.layout.image_bbox, page.bbox, b.bbox) for b in page_table_boxes]
        for table_idx, table_box in enumerate(page_table_boxes):
            for block_idx, block in enumerate(page.blocks):
                intersect_pct = block.intersection_pct(table_box)
                if intersect_pct > settings.BBOX_INTERSECTION_THRESH and block.block_type == "Table":
                    if table_idx not in table_insert_points:
                        table_insert_points[table_idx] = block_idx - len(blocks_to_remove) + table_idx # Where to insert the new table
                    blocks_to_remove.add(block_idx)

        new_page_blocks = []
        for block_idx, block in enumerate(page.blocks):
            if block_idx in blocks_to_remove:
                continue
            new_page_blocks.append(block)

        for table_idx, table_box in enumerate(page_table_boxes):
            if table_idx not in table_insert_points:
                continue

            if page.ocr_method == "surya":
                table_rows = get_table_surya(page, table_box)
            else:
                table_rows = get_table_pdftext(page, table_box)
            # Skip empty tables
            if len(table_rows) == 0:
                continue

            table_text = tabulate(table_rows, headers="firstrow", tablefmt="github", disable_numparse=True)
            table_block = Block(
                bbox=table_box,
                block_type="Table",
                pnum=pnum,
                lines=[Line(
                    bbox=table_box,
                    spans=[Span(
                        bbox=table_box,
                        span_id=f"{table_idx}_table",
                        font="Table",
                        font_size=0,
                        font_weight=0,
                        block_type="Table",
                        text=table_text
                    )]
                )]
            )
            insert_point = table_insert_points[table_idx]
            new_page_blocks.insert(insert_point, table_block)
            table_count += 1
        page.blocks = new_page_blocks
    return table_count

def table_detection(filename: str, pages: List[Page], max_pages: int):
    from transformers import (
        TableTransformerForObjectDetection,
        DetrFeatureExtractor
    )
    
    # Model setup
    THRESHOLD = 0.8
    table_detect_model = TableTransformerForObjectDetection.from_pretrained(
    "microsoft/table-transformer-detection"
)
    feature_extractor = DetrFeatureExtractor()

    doc = fitz.open(filename)
    length = len(doc)
    if max_pages:
        length = min(length, max_pages)
    
    for i_pg in range(length):
        extracted_data = extract_table(doc, i_pg, feature_extractor, table_detect_model, THRESHOLD=THRESHOLD)
        if extracted_data is None:
            continue

        (
            h_lines,
            v_lines,
            ocr_data,
            table_bbox,
            table_img_path,
        ) = extracted_data
        img = cv2.imread(table_img_path)
                
        print("H Lines: ", len(h_lines))
        print("H Lines: ", len(v_lines))
        
        h_lines.sort(key=lambda l: l.y)
        v_lines.sort(key=lambda l: l.x)
        rowwise_intersections = detect_rowwise_intersection(h_lines, v_lines)
        for p_r in rowwise_intersections:
            for p in p_r:
                p.draw(img)
        boxes = detect_boxes(rowwise_intersections)
        cells = get_cells(boxes, h_lines, v_lines)
        
        words_original = [
    {"x": x, "y": y, "width": width, "height": height, "text": text}
        for x, y, width, height, text in zip(
            ocr_data["left"],
            ocr_data["top"],
            ocr_data["width"],
            ocr_data["height"],
            ocr_data["text"],
        )
        if text.strip()
    ]
        fill_text_in_cells(words_original, cells, img)
        # row wise cell segregation
        rows = defaultdict(dict)
        for cell in cells:
            rows[cell.r][cell.c] = cell.text
            
        table_df = pd.DataFrame.from_dict(rows, orient="index")
        if table_df.empty:
            print("The DataFrame is empty")
            continue
        table_df = table_df.drop_duplicates(keep='last')
        table_df.columns = table_df.iloc[0]
        table_df = table_df[1:].reset_index(drop=True)
        table_df.to_csv(f"{i_pg}_table.csv", index=False)
        md = table_df.to_markdown(index=False)
        
        table_block = Block(
                bbox=table_bbox,
                block_type="Table",
                pnum=i_pg,
                lines=[Line(
                    bbox=table_bbox,
                    spans=[Span(
                        bbox=table_bbox,
                        span_id=f"{i_pg}_table",
                        font="Table",
                        font_size=0,
                        font_weight=0,
                        block_type="TABLE",
                        text=md
                    )]
                )]
            )
        pages[i_pg].blocks.append(table_block)



def get_page(pdf, page_num):
    # TODO: Add page check if page_num is valid
    page = pdf.load_page(page_num)
    pix = page.get_pixmap(dpi=180)
    image = PIL.Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return image


def ocr_img(image: PIL.Image):
    tesseract_config = "-l hin --oem 3 --psm 6"
    data = pytesseract.image_to_data(
        image, config=tesseract_config, output_type=pytesseract.Output.DICT
    )
    return data


def extract_table(pdf: fitz.Document, page_num: int, encoder, detector, THRESHOLD=0.8):
    image = get_page(pdf, page_num)

    encodings = encoder(image, return_tensors="pt")

    with torch.no_grad():
        outputs = detector(**encodings)
    width, height = image.size
    target_size = [(height, width)]
    results = encoder.post_process_object_detection(
        outputs, threshold=THRESHOLD, target_sizes=target_size
    )[0]

    if len(results["boxes"]) > 0:
        for idx, ex_box in enumerate(results["boxes"]):
            box = Rectangle.fromCoords(*ex_box)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                image_path = temp_file.name
                save_table_image(image, box, image_path)
                image = PIL.Image.open(image_path)
                img_cv2 = cv2.imread(image_path)
                ocr_data = ocr_img(image)

                horizontal_lines_bbox, vertical_line_bboxes = detect_borderlines(
                    image_path
                )
                text_line_bbox, text_line_height = detect_horizontal_textlines(
                    ocr_data, image
                )

                text_line_bbox = [l for l in text_line_bbox if l.width > l.height]

                _, _, _, new_horizontal_lines_bbox = filter_non_intersecting_lines(
                    text_line_bbox,
                    horizontal_lines_bbox,
                    horizontal_lines_height=text_line_height / 4,
                )

                horizontal_lines_bbox_clustered = cluster_horizontal_lines(
                    new_horizontal_lines_bbox, text_line_height
                )
                vertical_line_bboxes_clustered = cluster_vertical_lines(
                    vertical_line_bboxes, text_line_height
                )

                horizontal_lines_bbox_clustered_filt, _, _, _ = (
                    filter_non_intersecting_lines(
                        horizontal_lines_bbox_clustered,
                        vertical_line_bboxes_clustered,
                        vertical_lines_width=text_line_height / 8,
                    )
                )

                h_lines, v_lines = extend_lines(
                    img_cv2,
                    horizontal_lines_bbox_clustered_filt,
                    vertical_line_bboxes_clustered,
                    text_line_height / 8,
                )
                for h in h_lines:
                    h.draw(img_cv2)

                for v in v_lines:
                    v.draw(img_cv2)

                cv2.imwrite(f"out/pg_{page_num}.png", img_cv2)
                return h_lines, v_lines, ocr_data, ex_box, image_path        