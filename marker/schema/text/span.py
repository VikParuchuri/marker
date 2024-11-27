import html
import re
from typing import List, Literal

from marker.schema import BlockTypes
from marker.schema.blocks import Block


def cleanup_text(full_text):
    full_text = re.sub(r'(\n\s){3,}', '\n\n', full_text)
    full_text = full_text.replace('\xa0', ' ') # Replace non-breaking spaces
    return full_text


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

    def assemble_html(self, child_blocks, parent_structure):
        if self.ignore_for_output:
            return ""

        text = self.text

        # Remove trailing newlines
        replaced_newline = False
        while len(text) > 0 and text[-1] in ["\n", "\r"]:
            text = text[:-1]
            replaced_newline = True

        # Remove leading newlines
        while len(text) > 0 and text[0] in ["\n", "\r"]:
            text = text[1:]

        if replaced_newline and not text.endswith('-'):
            text += " "

        text = text.replace("-\n", "")  # Remove hyphenated line breaks from the middle of the span
        text = html.escape(text)
        text = cleanup_text(text)

        if len(text) > 3:
            if self.italic:
                return f"<i>{text}</i>"
            elif self.bold:
                return f"<b>{text}</b>"
        return text
