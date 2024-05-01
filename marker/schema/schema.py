from collections import Counter
from typing import List, Optional

from pydantic import BaseModel, field_validator
import ftfy

from marker.schema.bbox import multiple_boxes_intersect, BboxElement
from marker.settings import settings


class BlockType(BboxElement):
    block_type: str


class Span(BboxElement):
    text: str
    span_id: str
    font: str
    font_weight: float
    font_size: float
    block_type: Optional[str] = None


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
