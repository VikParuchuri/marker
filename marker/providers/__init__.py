from typing import List, Optional, Dict

from PIL import Image
from pydantic import BaseModel

from pdftext.schema import Reference

from marker.schema.polygon import PolygonBox
from marker.schema.text import Span
from marker.schema.text.line import Line
from marker.util import assign_config


class ProviderOutput(BaseModel):
    line: Line
    spans: List[Span]

    @property
    def raw_text(self):
        return "".join(span.text for span in self.spans)

ProviderPageLines = Dict[int, List[ProviderOutput]]

class BaseProvider:
    def __init__(self, filepath: str, config: Optional[BaseModel | dict] = None):
        assign_config(self, config)
        self.filepath = filepath

    def __len__(self):
        pass

    def get_images(self, idxs: List[int], dpi: int) -> List[Image.Image]:
        pass

    def get_page_bbox(self, idx: int) -> PolygonBox | None:
        pass

    def get_page_lines(self, idx: int) -> List[Line]:
        pass

    def get_page_refs(self, idx: int) -> List[Reference]:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        raise NotImplementedError
