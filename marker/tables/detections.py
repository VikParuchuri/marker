from typing import List
import cv2
import numpy as np
from marker.tables.schema import Line
import PIL.Image

def detect_borderlines(file_path: str, angle_threshold=1, vertical_slope_threshold=10):
    image = cv2.imread(file_path)
    if image is None:
        return None, None, None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (9, 9), 0)
    edges = cv2.Canny(blur, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=150, minLineLength=200, maxLineGap=10
    )

    horizontal_line_bboxes = []
    vertical_line_bboxes = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]

            # Horizontal line check
            if x2 - x1 != 0:  # To avoid division by zero
                slope = (y2 - y1) / (x2 - x1)
                if abs(slope) < np.tan(
                    np.radians(angle_threshold)
                ):  # Check for horizontal lines
                    min_x, max_x = min(x1, x2), max(x1, x2)
                    min_y, max_y = min(y1, y2), max(y1, y2)
                    horizontal_line_bboxes.append(
                        Line(min_x, min_y, max_x - min_x, max_y - min_y)
                    )

            # Vertical line check
            if (
                abs(x2 - x1) < np.tan(np.radians(90 - angle_threshold))
                or abs(slope) > vertical_slope_threshold
            ):  # Check for vertical lines
                min_x, max_x = min(x1, x2), max(x1, x2)
                min_y, max_y = min(y1, y2), max(y1, y2)
                vertical_line_bboxes.append(
                    Line(min_x, min_y, max_x - min_x, max_y - min_y)
                )

    return horizontal_line_bboxes, vertical_line_bboxes


def detect_horizontal_textlines(data, image: PIL.Image) -> tuple[List[Line], float]:
    heights = [
        data["height"][i] for i in range(len(data["text"])) if int(data["conf"][i]) > 0
    ]
    average_height = np.mean(heights)
    lines = []
    for i in range(len(data["text"])):
        if int(data["conf"][i]) > 0:
            word_center = data["top"][i] + data["height"][i] / 2
            found_line = False
            for line in lines:
                if any(
                    abs((data["top"][idx] + data["height"][idx] / 2) - word_center)
                    <= average_height / 2
                    for idx in line
                ):
                    line.append(i)
                    found_line = True
                    break
            if not found_line:
                lines.append([i])

    opencv_image = np.array(image)
    opencv_image = cv2.cvtColor(opencv_image, cv2.COLOR_RGB2BGR)
    line_bboxes = []
    for line in lines:
        centers = [
            (
                data["left"][i] + data["width"][i] // 2,
                data["top"][i] + data["height"][i] // 2,
            )
            for i in line
        ]
        avg_y = int(np.mean([c[1] for c in centers]))
        min_x = int(min(c[0] for c in centers)) - 10
        max_x = int(max(c[0] for c in centers)) + 10
        line_bboxes.append(
            Line(
                min_x,
                avg_y - int(average_height / 2),
                max_x - min_x,
                int(average_height),
            )
        )

    return line_bboxes, average_height


def filter_non_intersecting_lines(
    horizontal_lines: List[Line],
    vertical_lines: List[Line],
    vertical_lines_width=None,
    horizontal_lines_height=None,
):
    # Keep a copy of the original lines for final output
    original_horizontal_lines = horizontal_lines.copy()
    original_vertical_lines = vertical_lines.copy()

    # Modify the dimensions for intersection checking if specified
    if not vertical_lines_width is None:
        vertical_lines_width = int(np.ceil(vertical_lines_width))
        vertical_lines = [
            Line(vl.x, vl.y, vertical_lines_width, vl.height) for vl in vertical_lines
        ]

    if not horizontal_lines_height is None:
        horizontal_lines_height = int(np.ceil(horizontal_lines_height))
        horizontal_lines = [
            Line(hl.x, hl.y, hl.width, horizontal_lines_height)
            for hl in horizontal_lines
        ]

    # horizontal_rects = [Rectangle(x, y, w, h) for x, y, w, h in horizontal_lines]
    # vertical_rects = [Rectangle(x, y, w, h) for x, y, w, h in vertical_lines]

    # Use sets to keep track of indexes of intersecting lines
    intersecting_horizontal_indexes = set()
    intersecting_vertical_indexes = set()

    # Check for intersection between horizontal and vertical lines in one pass
    for i, h_rect in enumerate(horizontal_lines):
        for j, v_rect in enumerate(vertical_lines):
            if h_rect.overlaps(v_rect):
                intersecting_horizontal_indexes.add(i)
                intersecting_vertical_indexes.add(j)

    # Prepare the output lists using original line coordinates
    intersecting_horizontal_lines = [
        original_horizontal_lines[i] for i in intersecting_horizontal_indexes
    ]
    non_intersecting_horizontal_lines = [
        original_horizontal_lines[i]
        for i in range(len(original_horizontal_lines))
        if i not in intersecting_horizontal_indexes
    ]
    intersecting_vertical_lines = [
        original_vertical_lines[j] for j in intersecting_vertical_indexes
    ]
    non_intersecting_vertical_lines = [
        original_vertical_lines[j]
        for j in range(len(original_vertical_lines))
        if j not in intersecting_vertical_indexes
    ]

    return (
        intersecting_horizontal_lines,
        non_intersecting_horizontal_lines,
        intersecting_vertical_lines,
        non_intersecting_vertical_lines,
    )


def cluster_horizontal_lines(horizontal_lines_bbox: List[Line], h):
    horizontal_lines_bbox.sort(key=lambda x: x.y)
    clusters = []

    for line in horizontal_lines_bbox:
        added_to_cluster = False
        for cluster in clusters:
            avg_y = sum([line.y for line in cluster]) / len(cluster)
            if abs(line.y - avg_y) <= h:
                cluster.append(line)
                added_to_cluster = True
                break

        if not added_to_cluster:
            clusters.append([line])
    merged_lines = []
    for cluster in clusters:
        min_x = min(line.x for line in cluster)
        max_x = max((line.x + line.width) for line in cluster)
        # avg_y = sum(line[1] for line in cluster) // len(cluster)
        avg_y = int(np.median([line.y for line in cluster]))
        merged_lines.append(Line(min_x, avg_y, max_x - min_x, 1))

    return merged_lines


def cluster_vertical_lines(vertical_lines_bbox: List[Line], v):
    vertical_lines_bbox.sort(key=lambda x: x.x)
    clusters = []
    for line in vertical_lines_bbox:
        added_to_cluster = False

        for cluster in clusters:
            avg_x = sum([line.x for line in cluster]) / len(cluster)
            if abs(line.x - avg_x) <= v:
                cluster.append(line)
                added_to_cluster = True
                break

        if not added_to_cluster:
            clusters.append([line])

    merged_lines = []
    for cluster in clusters:
        min_y = min(line.y for line in cluster)
        max_y = max(line.y + line.height for line in cluster)
        avg_x = sum(line.x for line in cluster) // len(cluster)
        merged_lines.append(
            Line(
                avg_x,
                min_y,
                1,  # Using 1 as the width for the new line
                max_y - min_y,
            )
        )

    return merged_lines


def extend_lines(img, h_lines, v_lines, line_width):
    LEN_THRESHOLD = 40
    img_h, img_w, _ = img.shape
    checking_lines_left = []
    checking_lines_right = []
    for l in h_lines:
        x, y, w, h = l.tolist()
        checking_lines_left.append(
            Line(
                x - (LEN_THRESHOLD / 2),
                y + h - line_width,
                LEN_THRESHOLD,
                line_width + 10,
            )
        )
        checking_lines_right.append(
            Line(
                x + w - LEN_THRESHOLD / 2,
                y + h - line_width,
                LEN_THRESHOLD,
                line_width + 10,
            )
        )

    checking_lines_top = []
    checking_lines_bottom = []
    for l in v_lines:
        x, y, w, h = l.tolist()
        start_point = x - LEN_THRESHOLD, y - line_width
        checking_lines_top.append(Line(x, y - 10, line_width + 2, 40))
        checking_lines_bottom.append(
            Line(x + w - line_width, y + h - (LEN_THRESHOLD / 2), line_width + 2, 40)
        )
    new_h_lines = []
    for left, right in zip(checking_lines_left, checking_lines_right):
        left_overlapped = False
        right_overlapped = False
        for v in v_lines:
            x_v, y_v, w_v, h_v = v.tolist()
            if v.overlaps(left):
                left_overlapped = True
                left_pt = x_v, left.y

            if v.overlaps(right):
                right_overlapped = True
                right_pt = x_v, right.y

            if left_overlapped and right_overlapped:
                break

        if left_overlapped and right_overlapped:
            new_h_lines.append(
                Line(int(left_pt[0]), int(left_pt[1]), int(right_pt[0] - left_pt[0]), 1)
            )
        else:
            print("NOT overlapped")

    ## Vertical lines
    new_h_lines.insert(0, Line(0, 0, img_w, 1))
    new_h_lines.append(Line(0, img_h, img_w, 1))

    ## Overlapping vertical start top point to nearby horizontal line
    new_v_lines = []
    for top, bottom in zip(checking_lines_top, checking_lines_bottom):
        top_overlapped = False
        bottom_overlapped = False
        for h in new_h_lines:
            x_h, y_h, w_h, h_h = h.tolist()
            if h.overlaps(top):
                top_overlapped = True
                top_pt = top.x, h.y

            if h.overlaps(bottom):
                bottom_overlapped = True
                bottom_pt = bottom.x, h.y

            if top_overlapped and bottom_overlapped:
                break

        if top_overlapped and bottom_overlapped:
            new_v_lines.append(Line.fromCoords(*top_pt, *bottom_pt))
        else:
            print(top_overlapped, bottom_overlapped)
            print("V Line Not Overlapped")

    print("H Lines: ", len(new_h_lines), "V Lines: ", len(new_v_lines))
    return new_h_lines, new_v_lines