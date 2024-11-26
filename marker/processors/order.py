from statistics import mean

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document


class OrderProcessor(BaseProcessor):
    """
    A processor for sorting the blocks in order if needed.  This can help when the layout image was sliced.
    """
    block_types = tuple()

    def __call__(self, document: Document):
        for page in document.pages:
            if page.text_extraction_method != "pdftext":
                continue

            if not page.layout_sliced:
                continue

            block_idxs = {}
            for block_id in page.structure:
                block = document.get_block(block_id)
                spans = block.contained_blocks(document, (BlockTypes.Span, ))
                if len(spans) == 0:
                    continue

                block_idxs[block_id] = (spans[0].minimum_position + spans[-1].maximum_position) / 2

            for block_id in page.structure:
                if block_id in block_idxs and block_idxs[block_id] > 0:
                    continue
                block = document.get_block(block_id)
                prev_block = document.get_prev_block(block)
                next_block = document.get_next_block(block)

                while prev_block and prev_block.id not in block_idxs:
                    prev_block = document.get_prev_block(prev_block)

                if not prev_block:
                    while next_block and next_block.id not in block_idxs:
                        next_block = document.get_next_block(next_block)

                if not next_block and not prev_block:
                    block_idxs[block_id] = 0
                elif prev_block:
                    block_idxs[block_id] = block_idxs[prev_block.id] + 1
                else:
                    block_idxs[block_id] = block_idxs[next_block.id] - 1

            page.structure = sorted(page.structure, key=lambda x: block_idxs[x])

