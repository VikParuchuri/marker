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


def line_separator(block_text: str, line: MergedLine, block_type: str, new_column: bool, new_page: bool, new_block: bool) -> str:
    lowercase_letters = r'\p{Ll}|\d'
    hyphens = r'-—¬'

    line_starts_lowercase = regex.match(rf"^\s?[{lowercase_letters}]", line.text)
    has_reference = regex.match(r"^\[\d+\]\s+[A-Z]", line.text)
    has_numbered_item = regex.match(r"^\d+:\s+", line.text)

    if block_type in ["Text", "List-item", "Footnote", "Caption", "Figure"]:
        if has_reference or has_numbered_item:
            return block_text.lstrip() + "\n\n" + line.text.lstrip()
        elif line_starts_lowercase:
            if regex.compile(rf'.*[{lowercase_letters}][{hyphens}]\s?$', regex.DOTALL).match(block_text):
                # If block_text ends with a lowercase letter followed by a hyphen, remove the hyphen and join
                return regex.split(rf"[{hyphens}]\s?$", block_text)[0].rstrip() + line.text.lstrip()
            elif regex.compile(rf'.*[{hyphens}]\s?$', regex.DOTALL).match(block_text):
                # If block_text ends with a hyphen, simply join without adding space
                return block_text.rstrip() + line.text.lstrip()
            else:
                # Default: Join with a space
                return block_text + " " + line.text.lstrip()
        elif new_page and not line_starts_lowercase:
            # For new page and line does not start lowercase, add double newlines
            return block_text + "\n\n" + line.text.lstrip()
        elif new_block:
            # For new block, add double newlines
            return block_text + "\n\n" + line.text.lstrip()
        else:
            # General case for joining lines with a space
            return block_text + " " + line.text.lstrip()
    elif block_type in ["Title", "Section-header"]:
        return block_text + " " + line.text.lstrip()
    elif block_type in ["Formula"]:
        return block_text + "\n" + line.text.lstrip()
    elif block_type in ["Code", "Table"]:
        return block_text + "\n\n" + line.text.lstrip()
    else:
        return block_text + " " + line.text.lstrip()


def block_separator(prev_block: FullyMergedBlock, block: FullyMergedBlock):
    sep = "\n"
    if prev_block.block_type == "Text":
        sep = "\n\n"

    return sep + block.text

def merge_lines(blocks: List[List[MergedBlock]], max_block_gap=15, min_new_block_x_indent=10, min_newline_y_offset=11):
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
                x_indent = line_x_start - prev_line_x_start
                y_indent = line_y_start - prev_line_y_start

                new_column = line_x_start > prev_line_x_end
                new_block = first_line_in_block or \
                    ( # we consider it a new block when there's an x indent from the previous line and it's a new line (y indent)
                        x_indent > min_new_block_x_indent \
                        and y_indent > min_newline_y_offset
                    )
                new_page = first_line_in_block and first_block_in_page

                if block_text:
                    block_text = line_separator(block_text, line, block_type, new_column, new_page, new_block)
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
