from enum import Enum
from typing import Optional

from pydantic import BaseModel

from marker.v2.schema import BlockTypes


class RenderFormat(str, Enum):
    json = "json"
    markdown = "markdown"


class BaseRenderer:
    block_type: BlockTypes | None = None

    def __init__(self, config: Optional[BaseModel | dict] = None):
        if config:
            for k in config.model_fields:
                setattr(self, k, config[k])

    def __call__(self, document_output):
        # Children are in reading order
        raise NotImplementedError
