import re

import regex

from marker.schema import BlockTypes
from marker.schema.blocks import Block, BlockOutput

HYPHENS = r'-—¬'


def remove_tags(text):
    return re.sub(r'<[^>]+>', '', text)


def replace_last(string, old, new):
    matches = list(re.finditer(old, string))
    if not matches:
        return string
    last_match = matches[-1]
    return string[:last_match.start()] + new + string[last_match.end():]


def strip_trailing_hyphens(line_text, next_line_text, line_html) -> str:
    lowercase_letters = r'\p{Ll}'

    hyphen_regex = regex.compile(rf'.*[{HYPHENS}]\s?$', regex.DOTALL)
    next_line_starts_lowercase = regex.match(rf"^\s?[{lowercase_letters}]", next_line_text)

    if hyphen_regex.match(line_text) and next_line_starts_lowercase:
        line_html = replace_last(line_html, rf'[{HYPHENS}]', "")

    return line_html


class Line(Block):
    block_type: BlockTypes = BlockTypes.Line

    def assemble_html(self, document, child_blocks, parent_structure):
        template = ""
        for c in child_blocks:
            template += c.html

        raw_text = remove_tags(template).strip()
        structure_idx = parent_structure.index(self.id)
        if structure_idx < len(parent_structure) - 1:
            next_block_id = parent_structure[structure_idx + 1]
            next_line = document.get_block(next_block_id)
            next_line_raw_text = next_line.raw_text(document)
            template = strip_trailing_hyphens(raw_text, next_line_raw_text, template)
        else:
            template = template.strip(' ') # strip any trailing whitespace from the last line
        return template

    def render(self, document, parent_structure, section_hierarchy=None):
        child_content = []
        if self.structure is not None and len(self.structure) > 0:
            for block_id in self.structure:
                block = document.get_block(block_id)
                child_content.append(block.render(document, parent_structure, section_hierarchy))

        return BlockOutput(
            html=self.assemble_html(document, child_content, parent_structure),
            polygon=self.polygon,
            id=self.id,
            children=[],
            section_hierarchy=section_hierarchy
        )
