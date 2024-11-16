from typing import List, Literal

from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class Span(Block):
    block_type: BlockTypes = BlockTypes.Span

    text: str
    font: str
    font_weight: float
    font_size: float
    minimum_position: int
    maximum_position: int
    formats: List[Literal['plain', 'math', 'chemical', 'bold', 'italic']]

    @property
    def bold(self):
        return 'bold' in self.formats

    @property
    def italic(self):
        return 'italic' in self.formats

    def assemble_html(self, child_blocks):
        if len(self.text) > 3:
            if self.italic:
                return f"<i>{self.text}</i>"
            elif self.bold:
                return f"<b>{self.text}</b>"
        return self.text
