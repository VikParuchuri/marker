from PIL import Image, ImageDraw
import copy

from marker.tables.edges import get_vertical_lines

from marker.schema.bbox import rescale_bbox
import numpy as np


def get_column_lines(page, table_box, table_rows, align="l", tolerance=4):
    table_height = (table_box[3] - table_box[1]) * 2
    table_width = table_box[2] - table_box[0]
    img_size = (int(table_width), int(table_height))
    draw_img = Image.new("RGB", img_size)
    draw = ImageDraw.Draw(draw_img)
    for row in table_rows:
        for cell in row:
            line_bbox = list(copy.deepcopy(cell[0]))
            match align:
                case "l":
                    line_bbox[2] = line_bbox[0]
                case "r":
                    line_bbox[0] = line_bbox[2]
                case "c":
                    line_bbox[0] = line_bbox[0] + (line_bbox[2] - line_bbox[0]) / 2
                    line_bbox[2] = line_bbox[0]

            line_bbox[1] -= tolerance
            line_bbox[3] += tolerance
            line_bbox[0] -= table_box[0]
            line_bbox[2] -= table_box[0]
            line_bbox[1] -= table_box[1]
            line_bbox[3] -= table_box[1]
            draw.rectangle(line_bbox, outline="red", width=tolerance)

    np_img = np.array(draw_img, dtype=np.float32) / 255.0
    columns = get_vertical_lines(np_img, divisor=2, x_tolerance=10, y_tolerance=1)
    columns = sorted(columns, key=lambda x: x[0])

    # Remove short columns (single cells, probably)
    # Rescale coordinates back to image
    rescaled = []
    for c in columns:
        if c[3] - c[1] < table_height / 5:
            continue
        c[0] += table_box[0]
        c[2] += table_box[0]
        c[1] += table_box[1]
        c[3] += table_box[1]
        rescaled.append(c)
    return rescaled


def assign_cells_to_columns(page, table_box, rows, tolerance=5):
    return [[cell[1] for cell in row] for row in rows]
    alignments = ["l", "r", "c"]
    columns = {}
    for align in alignments:
        columns[align] = get_column_lines(page, table_box, rows, align=align)

    # Find the column alignment that is closest to the number of columns
    max_cols = max([len(r) for r in rows])
    columns = min(columns.items(), key=lambda x: abs(len(x) - max_cols))[1]

    formatted_rows = []
    for table_row in rows:
        formatted_row = []
        for cell_idx in range(len(table_row) - 1, -1, -1):
            cell = copy.deepcopy(table_row[cell_idx])
            cell_bbox = cell[0]

            found = False
            for j in range(len(columns) - 1, -1, -1):
                if columns[j][0] - tolerance < cell_bbox[0]:
                    if len(formatted_row) > 0:
                        prev_column = formatted_row[-1][0]
                        blanks = prev_column - j
                        if blanks > 1:
                            for b in range(1, blanks):
                                formatted_row.append((prev_column - b, ""))
                    formatted_row.append((j, cell[1]))
                    found = True
                    break
            if not found:
                formatted_row.append((cell_idx, cell[1]))
        formatted_rows.append(formatted_row[::-1])

    col_count = len(columns)
    clean_rows = []
    for row in formatted_rows:
        clean_row = []
        for col in range(col_count):
            found = False
            for cell in row:
                if cell[0] == col:
                    clean_row.append(cell)
                    found = True
                    break
            if not found:
                clean_row.append((col, ""))
        clean_rows.append([cell[1] for cell in clean_row])
    return clean_rows