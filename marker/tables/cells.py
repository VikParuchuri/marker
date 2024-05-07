from marker.schema.bbox import rescale_bbox, box_intersection_pct
from marker.schema.page import Page


def find_row_separators(page: Page, table_box, round_factor=4):
    top_edges = []
    bottom_edges = []

    line_boxes = [p.bbox for p in page.text_lines.bboxes]
    line_boxes = [rescale_bbox(page.text_lines.image_bbox, page.bbox, l) for l in line_boxes]
    line_boxes = [l for l in line_boxes if box_intersection_pct(l, table_box) > .8]

    min_count = len(line_boxes) / 3

    for cell in line_boxes:
        top_edges.append(cell[1] / round_factor * round_factor)
        bottom_edges.append(cell[3] / round_factor * round_factor)

    top_edges = [t for t in top_edges if top_edges.count(t) > min_count]
    bottom_edges = [b for b in bottom_edges if bottom_edges.count(b) > min_count]

    unique_top = sorted(list(set(top_edges)))
    unique_bottom = sorted(list(set(bottom_edges)))

    separators = min([unique_top, unique_bottom], key=len)

    # Add the top and bottom of the page as separators, to grab all possible cells
    separators.append(page.bbox[3])
    separators.insert(0, page.bbox[1])
    return separators


def find_column_separators(page: Page, table_box, round_factor=4):
    left_edges = []
    right_edges = []
    centers = []

    line_boxes = [p.bbox for p in page.text_lines.bboxes]
    line_boxes = [rescale_bbox(page.text_lines.image_bbox, page.bbox, l) for l in line_boxes]
    line_boxes = [l for l in line_boxes if box_intersection_pct(l, table_box) > .8]

    min_count = len(line_boxes) / 3
    for cell in line_boxes:
        left_edges.append(cell[0] / round_factor * round_factor)
        right_edges.append(cell[2] / round_factor * round_factor)
        centers.append((cell[0] + cell[2]) / 2 * round_factor / round_factor)

    left_edges = [l for l in left_edges if left_edges.count(l) > min_count]
    right_edges = [r for r in right_edges if right_edges.count(r) > min_count]
    centers = [c for c in centers if centers.count(c) > min_count]

    unique_left = sorted(list(set(left_edges)))
    unique_right = sorted(list(set(right_edges)))
    unique_center = sorted(list(set(centers)))

    # Find list with minimum length
    separators = min([unique_left, unique_right, unique_center], key=len)
    separators.append(page.bbox[2])
    separators.insert(0, page.bbox[0])
    return separators


def assign_cells_to_columns(page, table_box, rows, round_factor=4, tolerance=4):
    separators = find_column_separators(page, table_box, round_factor=round_factor)
    new_rows = []
    additional_column_index = 0
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
                column_index = len(separators) + additional_column_index
                additional_column_index += 1
            new_row[column_index] = cell[1]
            last_col_index = column_index
        additional_column_index = 0

        flat_row = []
        for cell_idx, cell in enumerate(sorted(new_row.items())):
            flat_row.extend([""] * (cell[0] - cell_idx) + [cell[1]])
        new_rows.append(flat_row)

    # Pad rows to have the same length
    max_row_len = max([len(r) for r in new_rows])
    for row in new_rows:
        while len(row) < max_row_len:
            row.append("")

    cols_to_remove = set()
    for idx, col in enumerate(zip(*new_rows)):
        col_total = sum([len(cell.strip()) > 0 for cell in col])
        if col_total == 0:
            cols_to_remove.add(idx)

    rows = []
    for row in new_rows:
        rows.append([col for idx, col in enumerate(row) if idx not in cols_to_remove])

    return rows
