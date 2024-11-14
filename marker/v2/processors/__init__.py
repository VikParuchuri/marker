from typing import Optional

from pydantic import BaseModel

from marker.v2.util import assign_config


class BaseProcessor:
    def __init__(self, config: Optional[BaseModel] = None):
        assign_config(self, config)