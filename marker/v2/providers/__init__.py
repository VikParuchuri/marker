from typing import List, Optional

from pydantic import BaseModel

from marker.v2.schema.text.line import Line
from marker.v2.util import assign_config


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
