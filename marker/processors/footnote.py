import re
from typing import List

from marker.processors import BaseProcessor
from marker.rules import RuleEngine
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.blocks import Block
from marker.schema.groups import PageGroup
from marker.schema.blocks.sectionheader import SectionHeader
from marker.schema.text import Line, Span
from marker.schema.polygon import PolygonBox


class FootnoteProcessor(BaseProcessor):
    """
    A processor for pushing footnotes to the bottom, and relabeling mislabeled text blocks.
    """
    block_types = (BlockTypes.Footnote,)

    def __init__(self, rule_engine: RuleEngine, config=None):
        self.rule_engine = rule_engine
        super().__init__(config)

    def __call__(self, document: Document):
        footnote_rules = self.rule_engine.get_rules("footnotes")
        if footnote_rules and footnote_rules.get("strategy") == "move_to_end":
            self.move_footnotes_to_end(document)
        else:
            for page in document.pages:
                self.push_footnotes_to_bottom(page, document)

        for page in document.pages:
            self.assign_superscripts(page, document)

    def move_footnotes_to_end(self, document: Document):
        """
        Moves all footnotes from all pages to the end of the document.
        """
        all_footnote_blocks: List[Block] = []
        for page in document.pages:
            # Get all footnote blocks that are direct children of the page
            footnote_blocks = [
                block for block in page.contained_blocks(document, self.block_types)
                if block.id in page.structure
            ]
            all_footnote_blocks.extend(footnote_blocks)

            # Remove footnotes from page structure
            if footnote_blocks:
                page.remove_structure_items([b.id for b in footnote_blocks])

        # Add all footnotes to the end of the last page's structure
        if all_footnote_blocks and document.pages:
            last_page = document.pages[-1]

            # Create a header for the footnotes section
            first_footnote = all_footnote_blocks[0]
            # Position the header slightly above the first footnote
            header_y = first_footnote.polygon.y_start - 10
            header_poly = PolygonBox.from_bbox([
                last_page.polygon.x_start,
                header_y - 5,
                last_page.polygon.x_end,
                header_y
            ])

            # Create the block components for the header
            header = SectionHeader(polygon=header_poly, heading_level=2, page_id=last_page.page_id)
            line = Line(polygon=header_poly, page_id=last_page.page_id)
            span = Span(
                text="Footnotes",
                polygon=header_poly,
                font="Helvetica-Bold",
                font_weight=700,
                font_size=12,
                minimum_position=0,
                maximum_position=len("Footnotes"),
                formats=["bold"],
                page_id=last_page.page_id
            )

            # Add blocks to the page to get IDs assigned
            last_page.add_full_block(header)
            last_page.add_full_block(line)
            last_page.add_full_block(span)

            # Link the blocks together in the structure
            line.structure = [span.id]
            header.structure = [line.id]

            # Add the new header and the footnotes to the page's main structure
            last_page.add_structure(header)
            for block in all_footnote_blocks:
                last_page.add_structure(block)

    def push_footnotes_to_bottom(self, page: PageGroup, document: Document):
        footnote_blocks = page.contained_blocks(document, self.block_types)

        # Push footnotes to the bottom
        for block in footnote_blocks:
            # Check if it is top-level
            if block.id in page.structure:
                # Move to bottom if it is
                page.structure.remove(block.id)
                page.add_structure(block)

    def assign_superscripts(self, page: PageGroup, document: Document):
        footnote_blocks = page.contained_blocks(document, self.block_types)

        for block in footnote_blocks:
            for span in block.contained_blocks(document, (BlockTypes.Span,)):
                if re.match(r"^[0-9\W]+", span.text):
                    span.has_superscript = True
                break
