from typing import List, Literal

from marker.v2.schema import Block


class Span(Block):
    block_type: str = "Span"

    text: str
    font: str
    font_weight: float
    font_size: float
    minimum_position: int
    maximum_position: int
    formats: List[Literal['plain', 'math', 'chemical', 'bold', 'italic']]
