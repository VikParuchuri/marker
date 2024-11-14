from marker.schema.block import Line
from marker.v2.renderers import BaseRenderer
from marker.v2.schema.text.span import Span


class DefaultRenderer(BaseRenderer):
    def __call__(self, document, block, children=None):
        text = ""
        if children is not None and len(children) > 0:
            for child in children:
                text += child.rendered
        if isinstance(block, Span):
            text = block.text
        elif isinstance(block, Line):
            text = text.rstrip() + "\n"
        else:
            text += "\n"

        return text
