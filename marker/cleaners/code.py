from marker.schema import Span, Line, Page
import re
from typing import List
import fitz as pymupdf


def is_code_linelen(lines, thresh=60):
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


def identify_code_blocks(blocks: List[Page]):
    code_block_count = 0
    font_info = None
    for p in blocks:
        stats = p.get_font_stats()
        if font_info is None:
            font_info = stats
        else:
            font_info += stats
    try:
        most_common_font = font_info.most_common(1)[0][0]
    except IndexError:
        print(f"Could not find most common font")
        most_common_font = None

    last_block = None
    for page in blocks:
        try:
            min_start = page.get_min_line_start()
        except IndexError:
            continue

        for block in page.blocks:
            if block.most_common_block_type() != "Text":
                last_block = block
                continue

            is_indent = []
            line_fonts = []
            for line in block.lines:
                fonts = [span.font for span in line.spans]
                line_fonts += fonts
                line_start = line.bbox[0]
                if line_start > min_start:
                    is_indent.append(True)
                else:
                    is_indent.append(False)
            comment_lines = comment_count([line.prelim_text for line in block.lines])
            is_code = [
                len(block.lines) > 3,
                sum([f != most_common_font for f in line_fonts]) > len(line_fonts) * .8,  # At least 80% of the fonts are not the most common, since code usually uses a different font from the main body text
                is_code_linelen(block.lines),
                (
                    sum(is_indent) > len(block.lines) * .2
                    or
                    comment_lines > len(block.lines) * .2
                 ), # 20% lines indented or 20% of the lines are comments
            ]

            # Check if previous block is code, and this block is indented
            is_code_prev = [
                last_block and last_block.most_common_block_type() == "Code",
                sum(is_indent) >= len(block.lines) * .8 # At least 80% indented
            ]

            if all(is_code) or all(is_code_prev):
                code_block_count += 1
                block.set_block_type("Code")

            last_block = block
    return code_block_count


def indent_blocks(blocks: List[Page]):
    span_counter = 0
    for page in blocks:
        for block in page.blocks:
            block_types = [span.block_type for line in block.lines for span in line.spans]
            if "Code" not in block_types:
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
            blank_line = False
            for line in lines:
                text = line[1]
                prefix = " " * int((line[0].x0 - min_left) / col_width)
                current_line_blank = len(text.strip()) == 0
                if blank_line and current_line_blank:
                    # Don't put multiple blank lines in a row
                    continue

                block_text += prefix + text + "\n"
                blank_line = current_line_blank

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