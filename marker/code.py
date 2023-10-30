from marker.schema import Span, Line, Page
import re
from typing import List
import fitz as pymupdf


def is_code_linelen(lines, thresh=50):
    # Decide based on chars per newline threshold
    total_alnum_chars = sum(len(re.findall(r'\w', line.prelim_text)) for line in lines)
    total_newlines = len(lines) - 1

    if total_alnum_chars == 0:
        return False

    ratio = total_alnum_chars / total_newlines
    return ratio < thresh


def identify_code_blocks(blocks: List[Page]):
    for page in blocks:
        try:
            common_height = page.get_line_height_stats().most_common(1)[0][0]
            common_start = page.get_line_start_stats().most_common(1)[0][0]
        except IndexError:
            continue

        for block in page.blocks:
            if len(block.lines) < 2:
                continue
            if block.most_common_block_type() != "Text":
                continue

            is_code = []
            for line in block.lines:
                fonts = [span.font for span in line.spans]
                monospace_font = any([font for font in fonts if "mono" in font.lower() or "prop" in font.lower()])
                line_height = line.bbox[3] - line.bbox[1]
                line_start = line.bbox[0]
                if line_height <= common_height and line_start > common_start and monospace_font:
                    is_code.append(True)
                else:
                    is_code.append(False)
            is_code = [
                sum(is_code) > len(block.lines) / 1.5,
                len(block.lines) > 4,
                is_code_linelen(block.lines)
            ]

            if all(is_code):
                block.set_block_type("Code")


def indent_blocks(blocks: List[Page]):
    span_counter = 0
    for page in blocks:
        for block in page.blocks:
            if block.most_common_block_type() != "Code":
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
                lines.append((pymupdf.Rect(line.bbox), text))

            block_text = ""
            for line in lines:
                text = line[1]
                prefix = " " * int((line[0].x0 - min_left) / col_width)
                block_text += prefix + text + "\n"
            new_span = Span(
                text=block_text,
                bbox=block.bbox,
                color=block.lines[0].spans[0].color,
                span_id=f"{span_counter}_fix_code",
                font=block.lines[0].spans[0].font,
                block_type="Code"
            )
            span_counter += 1
            block.lines = [Line(spans=[new_span], bbox=block.bbox)]