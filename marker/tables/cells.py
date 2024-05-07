from marker.schema.bbox import rescale_bbox, box_intersection_pct
from marker.schema.page import Page
from sklearn.cluster import DBSCAN
import numpy as np

from marker.settings import settings


def cluster_coords(coords):
    if len(coords) == 0:
        return []
    coords = np.array(sorted(set(coords))).reshape(-1, 1)

    clustering = DBSCAN(eps=5, min_samples=1).fit(coords)
    clusters = clustering.labels_

    separators = []
    for label in set(clusters):
        clustered_points = coords[clusters == label]
        separators.append(np.mean(clustered_points))

    separators = sorted(separators)
    return separators


def find_column_separators(page: Page, table_box, round_factor=4, min_count=1):
    left_edges = []
    right_edges = []
    centers = []

    line_boxes = [p.bbox for p in page.text_lines.bboxes]
    line_boxes = [rescale_bbox(page.text_lines.image_bbox, page.bbox, l) for l in line_boxes]
    line_boxes = [l for l in line_boxes if box_intersection_pct(l, table_box) > settings.BBOX_INTERSECTION_THRESH]

    for cell in line_boxes:
        left_edges.append(cell[0] / round_factor * round_factor)
        right_edges.append(cell[2] / round_factor * round_factor)
        centers.append((cell[0] + cell[2]) / 2 * round_factor / round_factor)

    left_edges = [l for l in left_edges if left_edges.count(l) > min_count]
    right_edges = [r for r in right_edges if right_edges.count(r) > min_count]
    centers = [c for c in centers if centers.count(c) > min_count]

    sorted_left = cluster_coords(left_edges)
    sorted_right = cluster_coords(right_edges)
    sorted_center = cluster_coords(centers)

    # Find list with minimum length
    separators = max([sorted_left, sorted_right, sorted_center], key=len)
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
            flat_row.append(cell[1])
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
