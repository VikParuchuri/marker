import math

import cv2
import numpy as np


def get_detected_lines_sobel(image):
    sobelx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3)

    scaled_sobel = np.uint8(255 * sobelx / np.max(sobelx))

    kernel = np.ones((4, 1), np.uint8)
    eroded = cv2.erode(scaled_sobel, kernel, iterations=1)
    scaled_sobel = cv2.dilate(eroded, kernel, iterations=3)

    return scaled_sobel


def get_line_angle(x1, y1, x2, y2):
    slope = (y2 - y1) / (x2 - x1)

    angle_radians = math.atan(slope)
    angle_degrees = math.degrees(angle_radians)

    return angle_degrees


def get_detected_lines(image, slope_tol_deg=10):
    new_image = image.astype(np.float32) * 255  # Convert to 0-255 range
    new_image = get_detected_lines_sobel(new_image)
    new_image = new_image.astype(np.uint8)

    edges = cv2.Canny(new_image, 50, 200, apertureSize=3)

    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, minLineLength=2, maxLineGap=100)

    line_info = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            bbox = [x1, y1, x2, y2]

            vertical = False
            if x2 == x1:
                vertical = True
            else:
                line_angle = get_line_angle(x1, y1, x2, y2)
                if 90 - slope_tol_deg < line_angle < 90 + slope_tol_deg:
                    vertical = True
                elif -90 - slope_tol_deg < line_angle < -90 + slope_tol_deg:
                    vertical = True
            if not vertical:
                continue

            if bbox[3] < bbox[1]:
                bbox[1], bbox[3] = bbox[3], bbox[1]
            if bbox[2] < bbox[0]:
                bbox[0], bbox[2] = bbox[2], bbox[0]
            if vertical:
                line_info.append(bbox)
    return line_info


def get_vertical_lines(image, divisor=2, x_tolerance=10, y_tolerance=1):
    vertical_lines = get_detected_lines(image)

    vertical_lines = sorted(vertical_lines, key=lambda x: x[0])
    for line in vertical_lines:
        for i in range(0, len(line)):
            line[i] = (line[i] // divisor) * divisor

    # Merge adjacent line segments together
    to_remove = []
    for i, line in enumerate(vertical_lines):
        for j, line2 in enumerate(vertical_lines):
            if j <= i:
                continue
            if line[0] != line2[0]:
                continue

            expanded_line1 = [line[0], line[1] - y_tolerance, line[2],
                              line[3] + y_tolerance]

            line1_points = set(range(int(expanded_line1[1]), int(expanded_line1[3])))
            line2_points = set(range(int(line2[1]), int(line2[3])))
            intersect_y = len(line1_points.intersection(line2_points)) > 0

            if intersect_y:
                vertical_lines[j][1] = min(line[1], line2[1])
                vertical_lines[j][3] = max(line[3], line2[3])
                to_remove.append(i)

    vertical_lines = [line for i, line in enumerate(vertical_lines) if i not in to_remove]

    # Remove redundant segments
    to_remove = []
    for i, line in enumerate(vertical_lines):
        if i in to_remove:
            continue
        for j, line2 in enumerate(vertical_lines):
            if j <= i or j in to_remove:
                continue
            close_in_x = abs(line[0] - line2[0]) < x_tolerance
            line1_points = set(range(int(line[1]), int(line[3])))
            line2_points = set(range(int(line2[1]), int(line2[3])))

            intersect_y = len(line1_points.intersection(line2_points)) > 0

            if close_in_x and intersect_y:
                # Keep the longer line and extend it
                if len(line2_points) > len(line1_points):
                    vertical_lines[j][1] = min(line[1], line2[1])
                    vertical_lines[j][3] = max(line[3], line2[3])
                    to_remove.append(i)
                else:
                    vertical_lines[i][1] = min(line[1], line2[1])
                    vertical_lines[i][3] = max(line[3], line2[3])
                    to_remove.append(j)

    vertical_lines = [line for i, line in enumerate(vertical_lines) if i not in to_remove]

    return vertical_lines