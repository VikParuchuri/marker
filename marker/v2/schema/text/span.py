from typing import Optional, Literal

from marker.v2.schema.baseblock import Block


class Span(Block):
    text: str
    font: str
    font_weight: float
    font_size: float
    minimum_position: int
    maximum_position: int
    format: Literal['plain', 'math', 'chemical', 'bold', 'italic']