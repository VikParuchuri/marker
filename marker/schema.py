from collections import Counter
from typing import List, Optional, Tuple

from pydantic import BaseModel, field_validator
import ftfy

from marker.bbox import boxes_intersect_pct, multiple_boxes_intersect
from marker.settings import settings


def find_span_type(span, page_blocks):
    block_type = "Text"
    for block in page_blocks:
        if boxes_intersect_pct(span.bbox, block.bbox):
            block_type = block.block_type
            break
    return block_type


class BboxElement(BaseModel):
    bbox: List[float]

    @field_validator('bbox')
    @classmethod
    def check_4_elements(cls, v: List[float]) -> List[float]:
        if len(v) != 4:
            raise ValueError('bbox must have 4 elements')
        return v

    @property
    def height(self):
        return self.bbox[3] - self.bbox[1]

    @property
    def width(self):
        return self.bbox[2] - self.bbox[0]

    @property
    def x_start(self):
        return self.bbox[0]

    @property
    def y_start(self):
        return self.bbox[1]

    @property
    def area(self):
        return self.width * self.height


class BlockType(BboxElement):
    block_type: str


class Span(BboxElement):
    text: str
    span_id: str
    font: str
    color: int
    ascender: Optional[float] = None
    descender: Optional[float] = None
    block_type: Optional[str] = None
    selected: bool = True


    @field_validator('text')
    @classmethod
    def fix_unicode(cls, text: str) -> str:
        return ftfy.fix_text(text)


class Line(BboxElement):
    spans: List[Span]

    @property
    def prelim_text(self):
        return "".join([s.text for s in self.spans])

    @property
    def start(self):
        return self.spans[0].bbox[0]


class Block(BboxElement):
    lines: List[Line]
    pnum: int

    @property
    def prelim_text(self):
        return "\n".join([l.prelim_text for l in self.lines])

    def contains_equation(self, equation_boxes=None):
        conditions = [s.block_type == "Formula" for l in self.lines for s in l.spans]
        if equation_boxes:
            conditions += [multiple_boxes_intersect(self.bbox, equation_boxes)]
        return any(conditions)

    def filter_spans(self, bad_span_ids):
        new_lines = []
        for line in self.lines:
            new_spans = []
            for span in line.spans:
                if not span.span_id in bad_span_ids:
                    new_spans.append(span)
            line.spans = new_spans
            if len(new_spans) > 0:
                new_lines.append(line)
        self.lines = new_lines

    def filter_bad_span_types(self):
        new_lines = []
        for line in self.lines:
            new_spans = []
            for span in line.spans:
                if span.block_type not in settings.BAD_SPAN_TYPES:
                    new_spans.append(span)
            line.spans = new_spans
            if len(new_spans) > 0:
                new_lines.append(line)
        self.lines = new_lines

    def most_common_block_type(self):
        counter = Counter([s.block_type for l in self.lines for s in l.spans])
        return counter.most_common(1)[0][0]

    def set_block_type(self, block_type):
        for line in self.lines:
            for span in line.spans:
                span.block_type = block_type


class Page(BboxElement):
    blocks: List[Block]
    pnum: int
    column_count: Optional[int] = None
    rotation: Optional[int] = None # Rotation degrees of the page

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

    def add_block_types(self, page_block_types):
        if len(page_block_types) != len(self.get_all_lines()):
            print(f"Warning: Number of detected lines {len(page_block_types)} does not match number of lines {len(self.get_all_lines())}")

        i = 0
        for block in self.blocks:
            for line in block.lines:
                if i < len(page_block_types):
                    line_block_type = page_block_types[i].block_type
                else:
                    line_block_type = "Text"
                i += 1
                for span in line.spans:
                    span.block_type = line_block_type

    def get_font_stats(self):
        fonts = [s.font for s in self.get_nonblank_spans()]
        font_counts = Counter(fonts)
        return font_counts

    def get_line_height_stats(self):
        heights = [l.bbox[3] - l.bbox[1] for l in self.get_nonblank_lines()]
        height_counts = Counter(heights)
        return height_counts

    def get_line_start_stats(self):
        starts = [l.bbox[0] for l in self.get_nonblank_lines()]
        start_counts = Counter(starts)
        return start_counts

    def get_min_line_start(self):
        starts = [l.bbox[0] for l in self.get_nonblank_lines() if l.spans[0].block_type == "Text"]
        if len(starts) == 0:
            raise IndexError("No lines found")
        return min(starts)

    @property
    def prelim_text(self):
        return "\n".join([b.prelim_text for b in self.blocks])

class MergedLine(BboxElement):
    text: str
    fonts: List[str]

    def most_common_font(self):
        counter = Counter(self.fonts)
        return counter.most_common(1)[0][0]


class MergedBlock(BboxElement):
    lines: List[MergedLine]
    pnum: int
    block_types: List[str]

    def most_common_block_type(self):
        counter = Counter(self.block_types)
        return counter.most_common(1)[0][0]


class FullyMergedBlock(BaseModel):
    text: str
    block_type: str
