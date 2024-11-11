from marker.schema.merged import MergedLine, MergedBlock, FullyMergedBlock
from marker.schema.page import Page
import re
import regex
from typing import List
from copy import deepcopy

from marker.settings import settings


def escape_markdown(text):
    # List of characters that need to be escaped in markdown
    characters_to_escape = r"[#]"
    # Escape each of these characters with a backslash
    escaped_text = re.sub(characters_to_escape, r'\\\g<0>', text)
    return escaped_text


def surround_text(s, char_to_insert):
    leading_whitespace = re.match(r'^(\s*)', s).group(1)
    trailing_whitespace = re.search(r'(\s*)$', s).group(1)
    stripped_string = s.strip()
    modified_string = char_to_insert + stripped_string + char_to_insert
    final_string = leading_whitespace + modified_string + trailing_whitespace
    return final_string


def merge_spans(pages: List[Page]) -> List[List[MergedBlock]]:
    merged_blocks = []
    for page in pages:
        page_blocks = []
        for blocknum, block in enumerate(page.blocks):
            block_lines = []
            for linenum, line in enumerate(block.lines):
                line_text = ""
                if len(line.spans) == 0:
                    continue
                fonts = []
                for i, span in enumerate(line.spans):
                    font = span.font.lower()
                    next_span = None
                    next_idx = 1
                    while len(line.spans) > i + next_idx:
                        next_span = line.spans[i + next_idx]
                        next_idx += 1
                        if len(next_span.text.strip()) > 2:
                            break

                    fonts.append(font)
                    span_text = span.text

                    # Don't bold or italicize very short sequences
                    # Avoid bolding first and last sequence so lines can be joined properly
                    if len(span_text) > 3 and 0 < i < len(line.spans) - 1:
                        if span.italic and (not next_span or not next_span.italic):
                            span_text = surround_text(span_text, "*")
                        elif span.bold and (not next_span or not next_span.bold):
                            span_text = surround_text(span_text, "**")
                    line_text += span_text
                block_lines.append(MergedLine(
                    text=line_text,
                    fonts=fonts,
                    bbox=line.bbox
                ))
            if len(block_lines) > 0:
                page_blocks.append(MergedBlock(
                    lines=block_lines,
                    pnum=page.pnum,
                    bbox=block.bbox,
                    block_type=block.block_type,
                    heading_level=block.heading_level
                ))
        if len(page_blocks) == 0:
            page_blocks.append(MergedBlock(
                lines=[],
                pnum=page.pnum,
                bbox=page.bbox,
                block_type="Text",
                heading_level=None
            ))
        merged_blocks.append(page_blocks)

    return merged_blocks


def block_surround(text, block_type, heading_level):
    if block_type == "Section-header":
        if not text.startswith("#"):
            asterisks = "#" * heading_level if heading_level is not None else "##"
            text = f"\n{asterisks} " + text.strip().title() + "\n"
    elif block_type == "Title":
        if not text.startswith("#"):
            text = "# " + text.strip().title() + "\n"
    elif block_type == "Table":
        text = "\n" + text + "\n"
    elif block_type == "List-item":
        text = escape_markdown(text.rstrip()) + "\n"
    elif block_type == "Code":
        text = "\n```\n" + text + "\n```\n"
    elif block_type == "Text":
        text = escape_markdown(text)
    elif block_type == "Formula":
        if text.strip().startswith("$$") and text.strip().endswith("$$"):
            text = text.strip()
            text = "\n" + text + "\n"
    elif block_type == "Caption":
        text = "\n" + escape_markdown(text) + "\n"
    return text


def line_separator(line1, line2, block_type, is_continuation=False):
    # Should cover latin-derived languages and russian
    lowercase_letters = r'\p{Lo}|\p{Ll}|\d'
    hyphens = r'-—¬'
    # Remove hyphen in current line if next line and current line appear to be joined
    hyphen_pattern = regex.compile(rf'.*[{lowercase_letters}][{hyphens}]\s?$', regex.DOTALL)
    if line1 and hyphen_pattern.match(line1) and regex.match(rf"^\s?[{lowercase_letters}]", line2):
        # Split on — or - from the right
        line1 = regex.split(rf"[{hyphens}]\s?$", line1)[0]
        return line1.rstrip() + line2.lstrip()

    all_letters = r'\p{L}|\d'
    sentence_continuations = r',;\(\—\"\'\*'
    sentence_ends = r'。ๆ\.?!'
    line_end_pattern = regex.compile(rf'.*[{lowercase_letters}][{sentence_continuations}]?\s?$', regex.DOTALL)
    line_start_pattern = regex.compile(rf'^\s?[{all_letters}]', regex.DOTALL)
    sentence_end_pattern = regex.compile(rf'.*[{sentence_ends}]\s?$', regex.DOTALL)

    text_blocks = ["Text", "List-item", "Footnote", "Caption", "Figure"]
    if block_type in ["Title", "Section-header"]:
        return line1.rstrip() + " " + line2.lstrip()
    elif block_type == "Formula":
        return line1 + "\n" + line2
    elif line_end_pattern.match(line1) and line_start_pattern.match(line2) and block_type in text_blocks:
        return line1.rstrip() + " " + line2.lstrip()
    elif is_continuation:
        return line1.rstrip() + " " + line2.lstrip()
    elif block_type in text_blocks and sentence_end_pattern.match(line1):
        return line1 + "\n\n" + line2
    elif block_type == "Table":
        return line1 + "\n\n" + line2
    else:
        return line1 + "\n" + line2


def block_separator(prev_block: FullyMergedBlock, block: FullyMergedBlock):
    sep = "\n"
    if prev_block.block_type == "Text":
        sep = "\n\n"

    return sep + block.text

lowercase_letters = r'\p{Lo}|\p{Ll}|\d'
hyphens = r'-—¬'

def merge_lines(blocks: List[List[MergedBlock]], max_block_gap=15):
    text_blocks = []
    prev_type = None
    prev_line = None
    block_text = ""
    block_type = ""
    prev_heading_level = None
    pnum = None

    for page_id, page in enumerate(blocks):
        # Insert pagination at every page boundary
        if settings.PAGINATE_OUTPUT:
            if block_text:
                text_blocks.append(
                    FullyMergedBlock(
                        text=block_surround(block_text, prev_type, prev_heading_level),
                        block_type=prev_type if prev_type else settings.DEFAULT_BLOCK_TYPE,
                        page_start=False,
                        pnum=pnum
                    )
                )
                block_text = ""
            text_blocks.append(
                FullyMergedBlock(
                    text="",
                    block_type="Text",
                    page_start=True,
                    pnum=page[0].pnum
                )
            )
        for block_id, block in enumerate(page):
            first_block_in_page = block_id == 0
            block_type = block.block_type
            if (block_type != prev_type and prev_type) or (block.heading_level != prev_heading_level and prev_heading_level):
                text_blocks.append(
                    FullyMergedBlock(
                        text=block_surround(block_text, prev_type, prev_heading_level),
                        block_type=prev_type if prev_type else settings.DEFAULT_BLOCK_TYPE,
                        page_start=False,
                        pnum=block.pnum
                    )
                )
                block_text = ""

            # Join lines in the block together properly
            for line_id, line in enumerate(block.lines):
                first_line_in_block = line_id == 0

                if prev_line is None:
                    prev_line = deepcopy(line)

                line_x_start, line_y_start, line_x_end, line_y_end = line.bbox
                prev_line_x_start, prev_line_y_start, prev_line_x_end, prev_line_y_end = prev_line.bbox
                vertical_dist = min(abs(line_y_start - prev_line_y_end), abs(line_y_end - prev_line_y_start))

                min_new_block_x_indent = 10
                min_new_block_x_offset = 5
                min_newline_y_offset = 6
                line_height_diff_tolerance = 1
                line_width_diff_tolerance = 1
                x_indent_tolerance = 1

                x_indent = line_x_start - prev_line_x_start
                x_offset = line_x_end - prev_line_x_end
                y_indent = prev_line_y_start - line_y_start
                y_offset = prev_line_y_end - line_y_end
                line_height_diff = prev_line.height - line.height
                line_width_diff = prev_line.width - line.width

                new_column_started = line_x_start > prev_line_x_end
                new_block = first_line_in_block or \
                    ( # we consider it a new block when there's an x indent or x offset from the previous line and it's a new line (y offset)
                        (
                            x_indent > min_new_block_x_indent
                        ) \
                        and abs(y_indent) > min_newline_y_offset
                    )
                is_continuation = ( # We consider a line to be a continuation if it's the same line, and the vertical distance is small
                    abs(line_height_diff) < line_height_diff_tolerance and abs(x_indent) < x_indent_tolerance \
                        and vertical_dist < max_block_gap
                    )
                new_page = first_line_in_block and first_block_in_page

                if block_text:
                    if block_type in ["Text", "List-item", "Footnote", "Caption", "Figure"]:
                        line_starts_lowercase = regex.match(rf"^\s?[{lowercase_letters}]", line.text)
                        if line_starts_lowercase:
                            if regex.compile(rf'.*[{lowercase_letters}][{hyphens}]\s?$', regex.DOTALL).match(block_text):
                                # If block_text ends with a letter followed by a hyphen, remove the hyphen and join
                                block_text = regex.split(rf"[{hyphens}]\s?$", block_text)[0].rstrip() + line.text.lstrip()
                            elif regex.compile(rf'.*[{hyphens}]\s?$', regex.DOTALL).match(block_text):
                                # If block_text ends with a hyphen, simply join without adding space
                                block_text = block_text.rstrip() + line.text.lstrip()
                            elif new_column_started or new_page:
                                # If new column started or a new page, add a space before joining
                                block_text = block_text + " " + line.text.lstrip()
                            else:
                                # Default: Join with a space
                                block_text = block_text + " " + line.text.lstrip()
                        elif new_page and not line_starts_lowercase:
                            # For new page and line does not start lowercase, add double newlines
                            block_text = block_text + "\n\n" + line.text.lstrip()
                        elif new_block:
                            # For new block, add double newlines
                            block_text = block_text + "\n\n" + line.text.lstrip()
                        else:
                            # General case for joining lines with a space
                            block_text = block_text + " " + line.text.lstrip()
                    elif block_type in ["Title", "Section-header"]:
                        block_text = block_text + " " + line.text.lstrip()
                    elif block_type in ["Formula"]:
                        block_text = block_text + "\n" + line.text.lstrip()
                    elif block_type in ["Code", "Table"]:
                        block_text = block_text + "\n\n" + line.text.lstrip()
                    else:
                        block_text = block_text + " " + line.text.lstrip()
                else:
                    block_text = line.text

                prev_line = line
            prev_type = block_type
            prev_heading_level = block.heading_level
            pnum = block.pnum
    # Append the final block
    text_blocks.append(
        FullyMergedBlock(
            text=block_surround(block_text, prev_type, prev_heading_level),
            block_type=block_type if block_type else settings.DEFAULT_BLOCK_TYPE,
            page_start=False,
            pnum=pnum
        )
    )

    text_blocks = [block for block in text_blocks if (block.text.strip() or block.page_start)]
    return text_blocks


def get_full_text(text_blocks):
    full_text = ""
    prev_block = None
    for block in text_blocks:
        if block.page_start:
            full_text += "\n\n{" + str(block.pnum) + "}" + settings.PAGE_SEPARATOR
        elif prev_block:
            full_text += block_separator(prev_block, block)
        else:
            full_text += block.text
        prev_block = block
    return full_text
