from marker.v2.schema import BlockTypes
from marker.v2.schema.text.line import Line
from marker.v2.schema.text.span import Span

TEXT_BLOCK_REGISTRY = {
    BlockTypes.Line: Line,
    BlockTypes.Span: Span,
}
