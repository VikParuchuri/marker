from typing import List, Optional, Dict

from pydantic import BaseModel

from marker.schema.text import Span
from marker.schema.text.line import Line
from marker.util import assign_config


class ProviderOutput(BaseModel):
    line: Line
    spans: List[Span]

ProviderPageLines = Dict[int, List[ProviderOutput]]

class BaseProvider:
    def __init__(self, filepath: str, config: Optional[BaseModel | dict] = None):
        assign_config(self, config)
        self.filepath = filepath

    def __len__(self):
        pass

    def get_image(self, idx: int, dpi: int):
        pass

    def get_page_bbox(self, idx: int) -> List[float]:
        pass

    def get_page_lines(self, idx: int) -> List[Line]:
        pass
