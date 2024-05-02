from marker.schema.bbox import merge_boxes, box_intersection_pct, rescale_bbox
from marker.schema.schema import Line, Span, Block
from marker.schema.page import Page
from tabulate import tabulate
from typing import List, Dict
import re


def replace_dots(text):
    dot_pattern = re.compile(r'(\s*\.\s*){4,}')
    dot_multiline_pattern = re.compile(r'.*(\s*\.\s*){4,}.*', re.DOTALL)

    if dot_multiline_pattern.match(text):
        text = dot_pattern.sub(' ', text)
    return text


def get_table_surya(page, table_box, y_tol=.005) -> List[List[str]]:
    table_rows = []
    row_y_coord = None
    table_row = []
    for block_idx, block in enumerate(page.blocks):
        for line_idx, line in enumerate(block.lines):
            line_bbox = line.bbox
            intersect_pct = box_intersection_pct(line_bbox, table_box)
            if intersect_pct < .5 or len(line.spans) == 0:
                continue
            normed_y_start = line_bbox[1] / page.height
            if row_y_coord is None or abs(normed_y_start - row_y_coord) < y_tol:
                table_row.extend([s.text for s in line.spans])
            else:
                table_rows.append(table_row)
                table_row = [s.text for s in line.spans]
            row_y_coord = normed_y_start
    if len(table_row) > 0:
        table_rows.append(table_row)
    return table_rows


def get_table_pdftext(page: Page, table_box) -> List[List[str]]:
    page_width = page.width
    table_rows = []
    for block_idx, block in enumerate(page.char_blocks):
        for line_idx, line in enumerate(block["lines"]):
            line_bbox = line["bbox"]
            intersect_pct = box_intersection_pct(line_bbox, table_box)
            if intersect_pct < .5:
                continue
            prev_end = None
            table_row = []
            table_cell = ""
            cell_bbox = None
            for span in line["spans"]:
                for char in span["chars"]:
                    x_start, y_start, x_end, y_end = char["bbox"]
                    if cell_bbox is None:
                        cell_bbox = char["bbox"]
                    else:
                        cell_bbox = merge_boxes(cell_bbox, char["bbox"])

                    x_start /= page_width
                    x_end /= page_width
                    if prev_end is None or x_start - prev_end < .01:
                        table_cell += char["char"]
                    else:
                        table_row.append(replace_dots(table_cell.strip()))
                        table_cell = char["char"]
                        cell_bbox = char["bbox"]
                    prev_end = x_end
                if len(table_cell) > 0:
                    table_row.append(replace_dots(table_cell.strip()))
                    table_cell = ""
            if len(table_row) > 0:
                table_rows.append(table_row)
    return table_rows


def arrange_table_rows(pages: List[Page]):
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
                if intersect_pct > .7 and block.block_type == "Table":
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

            max_row_len = max([len(r) for r in table_rows])
            for row in table_rows:
                while len(row) < max_row_len:
                    row.append("")

            table_text = tabulate(table_rows, headers="firstrow", tablefmt="github")
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