from marker.bbox import merge_boxes
from marker.schema import Line, Span, Block, Page
from typing import List
import re
from copy import deepcopy
import math


def merge_list_blocks(blocks: List[Page]):

    current_lines = []
    current_bbox = None
    debug = False

    ## do these loops infer the structure is
    ## blocks > pages > blocks > lines > spans

    for page in blocks:
        new_page_blocks = []
        pnum = page.pnum

        current_list_item_span = None

        for block in page.blocks:

            ## pass through the data that isn't list-items
            if block.most_common_block_type() != "List-item":

                ## handle the case of starting a new non-list item block with a dangling list item present
                ## close it out and clear the reference
                if current_list_item_span is not None:
                    current_lines.append(Line(spans=[current_list_item_span], bbox=current_list_item_span.bbox))
                    current_list_item_span = None


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

                if debug:
                    for line in block.lines:
                        for span in line.spans:
                            if span.text.strip():
                                print(f"[ypos: {str(span.bbox[1])[:3]},{str(span.bbox[3])[:3]}], Text: {span.text}")

                continue

            ## begin working on data that are list items
            ##current_lines.extend(block.lines)

            ## i have no idea what this does
            if current_bbox is None:
                current_bbox = block.bbox
            else:
                current_bbox = merge_boxes(current_bbox, block.bbox)
            
            ## extend creates a reference so this is also updating current_lines
            for line in block.lines:
                for span in line.spans:
                    trimmed_text = span.text.strip()
                    xpos = math.floor(span.bbox[0])
                    ypos = math.floor(span.bbox[1])
                    ypos2 = math.floor(span.bbox[3])
                    indent = math.floor((xpos - 48) / 18)
                    
                    if is_list_item_indicator(trimmed_text):
                        if current_list_item_span is not None:
                            ## since we're starting a new list item
                            ## and we already have on in the loop
                            ## write it out to where ever it will get to the output
                            ## then make a new one
                            ## Probably this means adding a new block with new lines with this span
                            ## but i dont' know where to put it or how to get it to interleave with
                            ## the rest of the items on the page
                            ## print("\n\nTODO: add this span to the output")
                            if debug:
                                print(current_list_item_span.text)
                            
                            ## appending the lines here using various bboxes creates mangled output
                            ## the items do not appear on new lines, even though they new lines and their bbox is assigned the same
                            ## as the start of the list-item 
                            ## printing the output looks perfect, but there's some magical something that occurs after this
                            ## that reorders the items on the page mysteriously
                            current_lines.append(Line(spans=[current_list_item_span], bbox=current_list_item_span.bbox))


                        ind = "\t" * indent
                        text = f" {ind}{span.text.strip()}"
                        if debug: 
                            text = f" {ind}[ypos: {ypos},{ypos2}]{span.text.strip()}"

                        current_list_item_span = Span(
                                                    bbox=span.bbox,
                                                    span_id=span.span_id,
                                                    font="List-item",
                                                    color=span.color,
                                                    block_type="List-item",
                                                    text=text
                                                )
                        span.text = ""  #preferably delete this but i don't know what that will do to the schema
                    else:
                        if current_list_item_span is not None:
                            # Append text to the current list item span
                            current_list_item_span.text += " " + span.text.strip()
                            current_list_item_span.bbox = merge_boxes(current_list_item_span.bbox, span.bbox)
                            span.text = "" #preferably delete this but i don't know what that will do to the schema
                #perferably delete empty lines but i don't know what that will do to the schema
                #note, the current_list_item spans blocks, and probably needs to span pages so this whole loop nesting process might need another layer                        

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