from typing import List
from marker.tables.schema import Rectangle, Line, Point, Cell
import copy

def find_intersections(h_line: Line, v_lines: List[Line]) -> List[Point]:
    """
    Find intersection points of horizontal and vertical lines.
    output: list of intersection points in format of (x, y)
    """
    intersections = []
    # Add some small margin widthwise to line
    new_h_line = Line(
        x1=h_line.x - 10, y1=h_line.y, width=h_line.width + 10, height=h_line.height
    )
    for v_l in v_lines:
        if v_l.overlaps(new_h_line):
            intersections.append(Point(v_l.x, h_line.y))
    return intersections


def detect_rowwise_intersection(
    h_lines: List[Line], v_lines: List[Line]
) -> List[List[Point]]:
    rowwise_intersections = []
    for h_line in h_lines:
        intersections = find_intersections(h_line, v_lines)
        # sort intersections from left to right
        intersections.sort(key=lambda x: x.x)
        rowwise_intersections.append(intersections)
    return rowwise_intersections


def detect_boxes(rowwise_intersections: List[List[Point]]) -> List[Rectangle]:
    boxes = []

    for r_i in range(len(rowwise_intersections) - 1):
        row = rowwise_intersections[r_i]
        # for each point in a row
        for c_i in range(len(row) - 1):
            intersec = row[c_i]
            # find a point where x - next_x < 10
            box = None
            for nr_i in range(r_i + 1, len(rowwise_intersections)):
                if box is not None:
                    break
                next_row = rowwise_intersections[nr_i]
                for next_ii in range(len(next_row)):
                    if box is not None:
                        break
                    next_i = next_row[next_ii]
                    if abs(intersec.x - next_i.x) < 10:
                        for j in range(next_ii + 1, len(next_row)):
                            if abs(row[c_i + 1].x - next_row[j].x) < 10:
                                box = Rectangle.fromPoints(intersec, next_row[j])
                                boxes.append(box)
                                break
    return boxes


def get_cells(boxes: List[Rectangle], h_lines: List[Line], v_lines: List[Line]):
    new_cells = []
    GAP = 10

    for box_id, box in enumerate(boxes):
        top_left = box.top_left
        bottom_right = box.bottom_right
        top_left = Point(top_left.x - GAP, top_left.y - GAP)
        bottom_right = Point(bottom_right.x + GAP, bottom_right.y + GAP)

        # Find Horizontal line passing
        horizontal_lines_passing = []
        for line_id, h_line in enumerate(h_lines):
            # Check if Y cord of a line is in between top_left and bottom_right
            # x, y, w, h = h_line
            line_y = h_line.y + (h_line.height / 2)

            if top_left.y <= line_y <= bottom_right.y:
                horizontal_lines_passing.append(line_id)

        # Find Vertical lines passing
        vertical_lines_passing = []
        for line_id, v_line in enumerate(v_lines):
            # check if X cord of line is in between top_left and bottom_right

            # x, y, w, h = v_line

            if top_left.x <= v_line.x <= bottom_right.x:
                vertical_lines_passing.append(line_id)
        row_spans = horizontal_lines_passing[1:]
        col_spans = vertical_lines_passing[1:]
        for r in row_spans:
            for c in col_spans:
                cell = Cell(box.top_left, box.bottom_right)
                cell.r = r
                cell.c = c
                new_cells.append(cell)

    return new_cells

def is_inside_cell(word, cell: Cell) -> bool:
    """Check if a word is inside the given rectangle."""
    word_x1, word_y1 = word["x"], word["y"]
    word_x2, word_y2 = word["x"] + word["width"], word["y"] + word["height"]

    return (
        cell.x1 - 10 <= word_x1 < cell.x2 + 10
        and cell.x1 - 10 <= word_x2 <= cell.x2 + 10
        and cell.y1 - 10 <= word_y1 < cell.y2 + 10
        and cell.y1 - 10 <= word_y2 <= cell.y2 + 10
    )


def sort_words_in_rect(words: list, img):

    words_list = copy.copy(words)
    sorted_words = []
    while len(words_list) != 0:
        per_line_words = []
        # Take the most upper rect
        top_rect = min(words_list, key=lambda w : w['y'])
        if top_rect['text'] == '|':
            words_list.remove(top_rect)
            continue
        line_y = top_rect["y"] + (top_rect["height"] / 2)
        
        # Find overlapping boxes
        for word in words_list:
            if word["y"] <= line_y and line_y <= (word["y"] + word["height"]):
                per_line_words.append(word)
        # Remove boxes
        for word in per_line_words:
            words_list.remove(word)
        
        per_line_words.sort(key=lambda w: w["x"])
        sorted_words.append(per_line_words)
    return sorted_words


def fill_text_in_cells(ocr_output, cells: List[Cell], img):
    """Get words inside each rectangle, sorted from top to bottom."""
    for cell in cells:
        words_in_rect = [word for word in ocr_output if is_inside_cell(word, cell)]
        # Sort words from top to bottom
        words_in_rect = sort_words_in_rect(words_in_rect, img)

        for line in words_in_rect:
            cell.text += " " + " ".join([w["text"] for w in line])
        cell.text = cell.text.strip()
        cell.text = cell.text.replace("|", "")
        
    # Sort boxes from top to bottom
    cells.sort(key=lambda c: c.y)
    # Sort boxes from left to right
    cells.sort(key=lambda b: b.x)

    # Adding indexes to each boxes
    for i, cell in enumerate(cells):
        cell.index = i

    return cells


