from marker.schema.bbox import rescale_bbox, box_intersection_pct
from marker.schema.page import Page
import numpy as np
from sklearn.cluster import DBSCAN
from marker.settings import settings


def cluster_coords(coords, row_count):
    if len(coords) == 0:
        return []
    coords = np.array(sorted(set(coords))).reshape(-1, 1)

    clustering = DBSCAN(eps=.01, min_samples=max(2, row_count // 4)).fit(coords)
    clusters = clustering.labels_

    separators = []
    for label in set(clusters):
        clustered_points = coords[clusters == label]
        separators.append(np.mean(clustered_points))

    separators = sorted(separators)
    return separators


def find_column_separators(page: Page, table_box, rows, round_factor=.002, min_count=1):
    left_edges = []
    right_edges = []
    centers = []

    line_boxes = [p.bbox for p in page.text_lines.bboxes]
    line_boxes = [rescale_bbox(page.text_lines.image_bbox, page.bbox, l) for l in line_boxes]
    line_boxes = [l for l in line_boxes if box_intersection_pct(l, table_box) > settings.BBOX_INTERSECTION_THRESH]

    pwidth = page.bbox[2] - page.bbox[0]
    pheight = page.bbox[3] - page.bbox[1]
    for cell in line_boxes:
        ncell = [cell[0] / pwidth, cell[1] / pheight, cell[2] / pwidth, cell[3] / pheight]
        left_edges.append(ncell[0] / round_factor * round_factor)
        right_edges.append(ncell[2] / round_factor * round_factor)
        centers.append((ncell[0] + ncell[2]) / 2 * round_factor / round_factor)

    left_edges = [l for l in left_edges if left_edges.count(l) > min_count]
    right_edges = [r for r in right_edges if right_edges.count(r) > min_count]
    centers = [c for c in centers if centers.count(c) > min_count]

    sorted_left = cluster_coords(left_edges, len(rows))
    sorted_right = cluster_coords(right_edges, len(rows))
    sorted_center = cluster_coords(centers, len(rows))

    # Find list with minimum length
    separators = max([sorted_left, sorted_right, sorted_center], key=len)
    separators.append(1)
    separators.insert(0, 0)
    return separators


def assign_cells_to_columns(page, table_box, rows, round_factor=.002, tolerance=.01):
    separators = find_column_separators(page, table_box, rows, round_factor=round_factor)
    additional_column_index = 0
    pwidth = page.bbox[2] - page.bbox[0]
    row_dicts = []

    for row in rows:
        new_row = {}
        last_col_index = -1
        for cell in row:
            left_edge = cell[0][0] / pwidth
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
        row_dicts.append(new_row)

    max_row_idx = 0
    for row in row_dicts:
        max_row_idx = max(max_row_idx, max(row.keys()))

    # Assign sorted cells to columns, account for blanks
    new_rows = []
    for row in row_dicts:
        flat_row = []
        for row_idx in range(1, max_row_idx + 1):
            if row_idx in row:
                flat_row.append(row[row_idx])
            else:
                flat_row.append("")
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