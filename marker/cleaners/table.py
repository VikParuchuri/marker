from marker.schema.bbox import merge_boxes, box_intersection_pct, rescale_bbox
from marker.schema.block import Line, Span, Block
from marker.schema.page import Page
from tabulate import tabulate
from typing import List, Dict
import re


def sort_char_blocks(blocks, tolerance=1.25):
    vertical_groups = {}
    for block in blocks:
        group_key = round(block["bbox"][1] / tolerance) * tolerance
        if group_key not in vertical_groups:
            vertical_groups[group_key] = []
        vertical_groups[group_key].append(block)

    # Sort each group horizontally and flatten the groups into a single list
    sorted_blocks = []
    for _, group in sorted(vertical_groups.items()):
        sorted_group = sorted(group, key=lambda x: x["bbox"][0])
        sorted_blocks.extend(sorted_group)

    return sorted_blocks


def replace_dots(text):
    dot_pattern = re.compile(r'(\s*\.\s*){4,}')
    dot_multiline_pattern = re.compile(r'.*(\s*\.\s*){4,}.*', re.DOTALL)

    if dot_multiline_pattern.match(text):
        text = dot_pattern.sub(' ', text)
    return text


def replace_newlines(text):
    # Replace all newlines
    newline_pattern = re.compile(r'[\r\n]+')
    return newline_pattern.sub(' ', text.strip())


def get_table_surya(page, table_box, space_tol=.01) -> List[List[str]]:
    table_rows = []
    table_row = []
    x_position = None
    for block_idx, block in enumerate(page.blocks):
        for line_idx, line in enumerate(block.lines):
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


def assign_cells_to_columns(rows, round_factor=4, tolerance=4):
    left_edges = []
    right_edges = []
    centers = []

    for row in rows:
        for cell in row:
            left_edges.append(cell[0][0] / round_factor * round_factor)
            right_edges.append(cell[0][2] / round_factor * round_factor)
            centers.append((cell[0][0] + cell[0][2]) / 2 * round_factor / round_factor)

    unique_left = sorted(list(set(left_edges)))
    unique_right = sorted(list(set(right_edges)))
    unique_center = sorted(list(set(centers)))

    # Find list with minimum length
    separators = min([unique_left, unique_right, unique_center], key=len)

    new_rows = []
    for row in rows:
        new_row = {}
        last_col_index = -1
        for cell in row:
            left_edge = cell[0][0]
            column_index = -1
            for i, separator in enumerate(separators):
                if left_edge - tolerance < separator and last_col_index < i:
                    column_index = i
                    break
            if column_index == -1:
                column_index = cell[0][0] # Assign a new column
            new_row[column_index] = cell[1]
            last_col_index = column_index

        flat_row = [cell[1] for cell in sorted(new_row.items())]
        min_column_index = min(new_row.keys())
        flat_row = [""] * min_column_index + flat_row
        new_rows.append(flat_row)

    return new_rows


def get_table_pdftext(page: Page, table_box, space_tol=.01) -> List[List[str]]:
    page_width = page.width
    table_rows = []
    table_cell = ""
    cell_bbox = None
    prev_end = None
    table_row = []
    sorted_char_blocks = sort_char_blocks(page.char_blocks)
    for block_idx, block in enumerate(sorted_char_blocks):
        sorted_block_lines = sort_char_blocks(block["lines"])
        for line_idx, line in enumerate(sorted_block_lines):
            line_bbox = line["bbox"]
            intersect_pct = box_intersection_pct(line_bbox, table_box)
            if intersect_pct < .5:
                continue
            for span in line["spans"]:
                for char in span["chars"]:
                    x_start, y_start, x_end, y_end = char["bbox"]
                    if cell_bbox is None:
                        cell_bbox = char["bbox"]
                    else:
                        cell_bbox = merge_boxes(cell_bbox, char["bbox"])

                    x_start /= page_width
                    x_end /= page_width
                    cell_content = replace_dots(replace_newlines(table_cell))
                    if prev_end is None or abs(x_start - prev_end) < space_tol: # Check if we are in the same cell
                        table_cell += char["char"]
                    elif x_start > prev_end - space_tol: # Check if we are on the same line
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
                    prev_end = x_end
    if len(table_cell) > 0:
        table_row.append((cell_bbox, replace_dots(replace_newlines(table_cell))))
    if len(table_row) > 0:
        table_rows.append(table_row)
    table_rows = assign_cells_to_columns(table_rows)
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