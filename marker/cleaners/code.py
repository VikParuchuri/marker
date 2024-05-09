from collections import Counter
from statistics import mean, median

from marker.schema.block import Span, Line
from marker.schema.page import Page
import re
from typing import List


def is_code_linelen(lines, thresh=80):
    # Decide based on chars per newline threshold
    total_alnum_chars = sum(len(re.findall(r'\w', line.prelim_text)) for line in lines)
    total_newlines = max(len(lines) - 1, 1)

    if total_alnum_chars == 0:
        return False

    ratio = total_alnum_chars / total_newlines
    return ratio < thresh


def comment_count(lines):
    pattern = re.compile(r"^(//|#|'|--|/\*|'''|\"\"\"|--\[\[|<!--|%|%{|\(\*)")
    return sum([1 for line in lines if pattern.match(line)])


def identify_code_blocks(pages: List[Page]):
    code_block_count = 0
    font_sizes = []
    line_heights = []
    for page in pages:
        font_sizes += page.get_font_sizes()
        line_heights += page.get_line_heights()

    avg_font_size = None
    avg_line_height = None
    if len(font_sizes) > 0:
        avg_line_height = median(line_heights)
        avg_font_size = mean(font_sizes)

    for page in pages:
        for block in page.blocks:
            if block.block_type != "Text":
                last_block = block
                continue

            # Ensure we have lines and spans
            if len(block.lines) == 0:
                continue
            if sum([len(line.spans) for line in block.lines]) == 0:
                continue

            min_start = block.get_min_line_start()

            is_indent = []
            line_fonts = []
            line_font_sizes = []
            block_line_heights = []
            for line in block.lines:
                line_fonts += [span.font for span in line.spans]
                line_font_sizes += [span.font_size for span in line.spans]
                block_line_heights.append(line.bbox[3] - line.bbox[1])

                is_indent.append(line.bbox[0] > min_start)

            comment_lines = comment_count([line.prelim_text for line in block.lines])
            is_code = [
                len(block.lines) > 3,
                is_code_linelen(block.lines),
                sum(is_indent) + comment_lines > len(block.lines) * .7, # Indentation and comments are a majority
            ]

            if avg_font_size is not None:
                font_checks = [
                    mean(line_font_sizes) <= avg_font_size * .8, # Lower than average font size and line height
                    mean(block_line_heights) < avg_line_height * .8
                ]
                is_code += font_checks

            if all(is_code):
                code_block_count += 1
                block.block_type = "Code"

    return code_block_count


def indent_blocks(pages: List[Page]):
    span_counter = 0
    for page in pages:
        for block in page.blocks:
            if block.block_type != "Code":
                continue

            lines = []
            min_left = 1000  # will contain x- coord of column 0
            col_width = 0  # width of 1 char
            for line in block.lines:
                text = ""
                min_left = min(line.bbox[0], min_left)
                for span in line.spans:
                    if col_width == 0 and len(span.text) > 0:
                        col_width = (span.bbox[2] - span.bbox[0]) / len(span.text)
                    text += span.text
                lines.append((line.bbox, text))

            block_text = ""
            blank_line = False
            for line in lines:
                text = line[1]
                if col_width == 0:
                    prefix = ""
                else:
                    prefix = " " * int((line[0][0] - min_left) / col_width)
                current_line_blank = len(text.strip()) == 0
                if blank_line and current_line_blank:
                    # Don't put multiple blank lines in a row
                    continue

                block_text += prefix + text + "\n"
                blank_line = current_line_blank

            new_span = Span(
                text=block_text,
                bbox=block.bbox,
                span_id=f"{span_counter}_fix_code",
                font=block.lines[0].spans[0].font,
                font_weight=block.lines[0].spans[0].font_weight,
                font_size=block.lines[0].spans[0].font_size,
            )
            span_counter += 1
            block.lines = [Line(spans=[new_span], bbox=block.bbox)]