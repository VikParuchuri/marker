from marker.bbox import merge_boxes
from marker.schema import Line, Span, Block, Page
from typing import List
import re
import textwrap
from marker.bbox import merge_boxes
from marker.schema import Line, Span, Block, Page
from copy import deepcopy
from tabulate import tabulate
from typing import List
import math


def merge_list_blocks(blocks: List[Page]):

    current_lines = []
    current_bbox = None
    for page in blocks:
        new_page_blocks = []
        pnum = page.pnum

        current_list_item_span = None

        for block in page.blocks:
            if block.most_common_block_type() != "List-item":
                if len(current_lines) > 0:
                    new_block = Block(
                        lines=deepcopy(current_lines),
                        pnum=pnum,
                        bbox=current_bbox
                    )
                    new_page_blocks.append(new_block)
                    current_lines = []
                    current_bbox = None

                new_page_blocks.append(block)
                continue

            current_lines.extend(block.lines)
            if current_bbox is None:
                current_bbox = block.bbox
            else:
                current_bbox = merge_boxes(current_bbox, block.bbox)
            
            for line in block.lines:
                for span in line.spans:
                    trimmed_text = span.text.strip()
                    xpos = math.floor(span.bbox[0])
                    indent = math.floor((xpos - 48) / 18)
                    
                    if is_list_item_indicator(trimmed_text):
                        if current_list_item_span is not None:
                            ## since we're starting a new list item
                            ## and we already have on in the loop
                            ## write it out to whereever it will get to the output
                            ## then make a new one
                            print("TODO: add this span to the output")
                            ##print(current_list_item_span)


                        ind = "\t" * indent
                        text = f" {ind}[{xpos}-{indent}]{span.text}"
                        current_list_item_span = Span(
                                                    bbox=span.bbox,
                                                    span_id=span.span_id,
                                                    font="List-item",
                                                    color=span.color,
                                                    block_type="List-item",
                                                    text=text
                                                )
                        span.text = ""
                    else:
                        if current_list_item_span is not None:
                            # Append text to the current list item span
                            current_list_item_span.text += " " + span.text.strip()
                            span.text = ""

            #note, the current_list_item spans blocks                        

        if len(current_lines) > 0:
            new_block = Block(
                lines=deepcopy(current_lines),
                pnum=pnum,
                bbox=current_bbox
            )

            new_page_blocks.append(new_block)
            current_lines = []
            current_bbox = None

        page.blocks = new_page_blocks

def create_new_lists(blocks: List[Page]):
    return None

def is_list_item_indicator(text):
    # Regular expression to match list item indicators (e.g., bullets, alphabetic, numeric, roman numerals)
    pattern = r'^(\s*[\u2022\u25E6\u25AA\u25AB\u25CF]|(?:[ivxlcdm]+\.)|(?:[a-zA-Z]\.)|(?:\d+\.)|\(\d+\))\s*'
    return re.match(pattern, text.strip()) is not None