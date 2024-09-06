from marker.schema.bbox import merge_boxes, box_intersection_pct, rescale_bbox
from marker.schema.block import Line, Span, Block
from marker.schema.page import Page
from tabulate import tabulate
from typing import List

from marker.settings import settings
from marker.tables.cells import assign_cells_to_columns
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
            if intersect_pct < settings.TABLE_INTERSECTION_THRESH or len(line.spans) == 0:
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
    new_line_start_x = table_box[0] + table_width * .3
    table_width_pct = (table_width / page_width) * .95

    for block_idx, block in enumerate(sorted_char_blocks):
        sorted_lines = sort_table_blocks(block["lines"])
        for line_idx, line in enumerate(sorted_lines):
            line_bbox = line["bbox"]
            intersect_pct = box_intersection_pct(line_bbox, table_box)
            if intersect_pct < settings.TABLE_INTERSECTION_THRESH:
                continue
            for span in line["spans"]:
                for char in span["chars"]:
                    x_start, y_start, x_end, y_end = char["bbox"]
                    x_start /= page_width
                    x_end /= page_width
                    fullwidth_cell = False

                    if cell_bbox is not None:
                        # Find boundaries of cell bbox before merging
                        cell_x_start, cell_y_start, cell_x_end, cell_y_end = cell_bbox
                        cell_x_start /= page_width
                        cell_x_end /= page_width

                        fullwidth_cell = cell_x_end - cell_x_start >= table_width_pct

                    cell_content = replace_dots(replace_newlines(table_cell))
                    if cell_bbox is None: # First char
                        table_cell += char["char"]
                        cell_bbox = char["bbox"]
                    # Check if we are in the same cell, ensure cell is not full table width (like if stray text gets included in the table)
                    elif (cell_x_start - space_tol < x_start < cell_x_end + space_tol) and not fullwidth_cell:
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

    total_cells = sum([len(row) for row in table_rows])
    if total_cells > 0:
        table_rows = assign_cells_to_columns(page, table_box, table_rows)
        return table_rows
    else:
        return []


def merge_tables(page_table_boxes):
    # Merge tables that are next to each other
    expansion_factor = 1.02
    shrink_factor = .98
    ignore_boxes = set()
    for i in range(len(page_table_boxes)):
        if i in ignore_boxes:
            continue
        for j in range(i + 1, len(page_table_boxes)):
            if j in ignore_boxes:
                continue
            expanded_box1 = [page_table_boxes[i][0] * shrink_factor, page_table_boxes[i][1],
                             page_table_boxes[i][2] * expansion_factor, page_table_boxes[i][3]]
            expanded_box2 = [page_table_boxes[j][0] * shrink_factor, page_table_boxes[j][1],
                             page_table_boxes[j][2] * expansion_factor, page_table_boxes[j][3]]
            if box_intersection_pct(expanded_box1, expanded_box2) > 0:
                page_table_boxes[i] = merge_boxes(page_table_boxes[i], page_table_boxes[j])
                ignore_boxes.add(j)

    return [b for i, b in enumerate(page_table_boxes) if i not in ignore_boxes]


def format_tables(pages: List[Page]):
    # Formats tables nicely into github flavored markdown
    table_count = 0
    for page in pages:
        table_insert_points = {}
        blocks_to_remove = set()
        pnum = page.pnum

        page_table_boxes = [b for b in page.layout.bboxes if b.label == "Table"]
        page_table_boxes = [rescale_bbox(page.layout.image_bbox, page.bbox, b.bbox) for b in page_table_boxes]
        page_table_boxes = merge_tables(page_table_boxes)

        for table_idx, table_box in enumerate(page_table_boxes):
            for block_idx, block in enumerate(page.blocks):
                intersect_pct = block.intersection_pct(table_box)
                if intersect_pct > settings.TABLE_INTERSECTION_THRESH and block.block_type == "Table":
                    if table_idx not in table_insert_points:
                        table_insert_points[table_idx] = max(0, block_idx - len(blocks_to_remove)) # Where to insert the new table
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

            table_rows = [
                [cell.replace('\n', ' <br> ') if '\n' in cell else cell for cell in row]
                for row in table_rows
            ]

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
            insert_point = min(insert_point, len(new_page_blocks))
            new_page_blocks.insert(insert_point, table_block)
            table_count += 1
        page.blocks = new_page_blocks
    return table_count