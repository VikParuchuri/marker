from marker.v2.renderers import BaseRenderer
from marker.v2.schema import BlockTypes


class SpanRenderer(BaseRenderer):
    block_type = BlockTypes.Span

    def __call__(self, document, block, children=None):
        return block.text