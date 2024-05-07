from collections import defaultdict

from marker.schema.bbox import merge_boxes, box_intersection_pct, rescale_bbox
from marker.schema.block import Line, Span, Block
from marker.schema.page import Page
from tabulate import tabulate
from typing import List

from marker.tables.cells import assign_cells_to_columns, find_row_separators, find_column_separators
from marker.tables.utils import sort_table_blocks, replace_dots, replace_newlines


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
    table_rows = assign_cells_to_columns(table_rows)
    return table_rows


def get_table_pdftext(page: Page, table_box, space_tol=.01) -> List[List[str]]:
    page_width = page.width
    table_rows = []
    table_cell = ""
    cell_bbox = None
    prev_char = False
    table_row = []
    sorted_char_blocks = sort_table_blocks(page.char_blocks)

    for block_idx, block in enumerate(sorted_char_blocks):
        sorted_lines = sort_table_blocks(block["lines"])
        for line_idx, line in enumerate(sorted_lines):
            line_bbox = line["bbox"]
            intersect_pct = box_intersection_pct(line_bbox, table_box)
            if intersect_pct < .7:
                continue
            for span in line["spans"]:
                for char in span["chars"]:
                    x_start, y_start, x_end, y_end = char["bbox"]

                    if cell_bbox is None:
                        cell_bbox = char["bbox"]
                    else:
                        # Find boundaries of cell bbox before merging
                        cell_x_start, cell_y_start, cell_x_end, cell_y_end = cell_bbox
                        cell_x_start /= page_width
                        cell_x_end /= page_width

                        cell_bbox = merge_boxes(cell_bbox, char["bbox"])

                    x_start /= page_width
                    x_end /= page_width

                    cell_content = replace_dots(replace_newlines(table_cell))
                    if not prev_char: # First char
                        table_cell += char["char"]
                    elif cell_x_start - space_tol < x_start < cell_x_end + space_tol: # Check if we are in the same cell
                        table_cell += char["char"]
                    elif x_start > cell_x_end - space_tol: # Same line, new cell, check against cell bbox
                        if len(table_cell) > 0:
                            table_row.append((cell_bbox, cell_content))
                        table_cell = char["char"]
                        cell_bbox = char["bbox"]
                    else: # New line and cell
                        if len(table_cell) > 0:
                            table_row.append((cell_bbox, cell_content))
                        table_cell = char["char"]
                        cell_bbox = char["bbox"]
                        if len(table_row) > 0:
                            table_rows.append(table_row)
                        table_row = []
                    prev_char = True

    if len(table_cell) > 0:
        table_row.append((cell_bbox, replace_dots(replace_newlines(table_cell))))
    if len(table_row) > 0:
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