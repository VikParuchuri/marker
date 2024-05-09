from collections import Counter
from typing import List, Optional, Dict, Any

from marker.schema.bbox import BboxElement
from marker.schema.block import Block, Span
from surya.schema import TextDetectionResult, LayoutResult, OrderResult


class Page(BboxElement):
    blocks: List[Block]
    pnum: int
    rotation: Optional[int] = None # Rotation degrees of the page
    text_lines: Optional[TextDetectionResult] = None
    layout: Optional[LayoutResult] = None
    order: Optional[OrderResult] = None
    ocr_method: Optional[str] = None # One of "surya" or "tesseract"
    char_blocks: Optional[List[Dict]] = None # Blocks with character-level data from pdftext
    images: Optional[List[Any]] = None # Images to save along with the page, need Any to avoid pydantic error

    def get_nonblank_lines(self):
        lines = self.get_all_lines()
        nonblank_lines = [l for l in lines if l.prelim_text.strip()]
        return nonblank_lines

    def get_all_lines(self):
        lines = [l for b in self.blocks for l in b.lines]
        return lines

    def get_nonblank_spans(self) -> List[Span]:
        lines = [l for b in self.blocks for l in b.lines]
        spans = [s for l in lines for s in l.spans if s.text.strip()]
        return spans

    def get_font_sizes(self):
        font_sizes = [s.font_size for s in self.get_nonblank_spans()]
        return font_sizes

    def get_line_heights(self):
        heights = [l.bbox[3] - l.bbox[1] for l in self.get_nonblank_lines()]
        return heights

    @property
    def prelim_text(self):
        return "\n".join([b.prelim_text for b in self.blocks])
