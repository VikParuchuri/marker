import re
from typing import List, Optional

from marker.v2.renderers import BaseRenderer
from marker.v2.schema import BlockTypes
from marker.v2.schema.text import Span


def surround_text(s, char_to_insert):
    leading_whitespace = re.match(r'^(\s*)', s).group(1)
    trailing_whitespace = re.search(r'(\s*)$', s).group(1)
    stripped_string = s.strip()
    modified_string = char_to_insert + stripped_string + char_to_insert
    final_string = leading_whitespace + modified_string + trailing_whitespace
    return final_string


class LineRenderer(BaseRenderer):
    block_type = BlockTypes.Line

    def __call__(self, document, block, children: Optional[List[Span]] = None):
        text = ""
        for i, child in enumerate(children):
            next_span = None
            next_idx = i + 1
            while len(children) > next_idx:
                next_span = children[next_idx]
                next_idx += 1
                if len(next_span.text.strip()) > 0:
                    break
            span_text = child.rendered

            # Don't bold or italicize very short sequences
            # Avoid bolding first and last sequence so lines can be joined properly
            if len(span_text) > 3 and 0 < i < len(children) - 1:
                if child.italic and (not next_span or not next_span.italic):
                    span_text = surround_text(span_text, "*")
                elif child.bold and (not next_span or not next_span.bold):
                    span_text = surround_text(span_text, "**")
            text += span_text
        return text