from typing import List, Literal

from marker.v2.schema.blocks import Block


class Span(Block):
    block_type: str = "Span"

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

    def assemble_html(self, child_blocks, parent_structure):
        text = self.text
        text = text.replace("-\n", "")  # Remove hyphenated line breaks

        # Remove trailing newlines
        replaced_newline = False
        while len(text) > 0 and text[-1] in ["\n", "\r"]:
            text = text[:-1]
            replaced_newline = True

        # Remove leading newlines
        while len(text) > 0 and text[0] in ["\n", "\r"]:
            text = text[1:]

        if replaced_newline:
            text += " "

        if len(text) > 3:
            if self.italic:
                return f"<i>{text}</i>"
            elif self.bold:
                return f"<b>{text}</b>"
        return text
