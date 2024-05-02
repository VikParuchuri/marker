from typing import List, Optional

from pydantic import field_validator
import ftfy

from marker.schema.bbox import BboxElement
from marker.settings import settings


class BlockType(BboxElement):
    block_type: str


class Span(BboxElement):
    text: str
    span_id: str
    font: str
    font_weight: float
    font_size: float
    bold: Optional[bool] = None
    italic: Optional[bool] = None


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
    block_type: Optional[str] = None

    @property
    def prelim_text(self):
        return "\n".join([l.prelim_text for l in self.lines])

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
                if self.block_type not in settings.BAD_SPAN_TYPES:
                    new_spans.append(span)
            line.spans = new_spans
            if len(new_spans) > 0:
                new_lines.append(line)
        self.lines = new_lines

    def font_info(self, prop="font"):
        font_info = []
        for line in self.lines:
            for span in line.spans:
                font_info.append(getattr(span, prop))
        return font_info


