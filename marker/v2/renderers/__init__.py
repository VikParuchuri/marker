from typing import Optional

from pydantic import BaseModel

from marker.v2.schema import BlockTypes
from marker.v2.util import assign_config


class BaseRenderer:
    block_type: BlockTypes | None = None

    def __init__(self, config: Optional[BaseModel | dict] = None):
        assign_config(self, config)

    def __call__(self, document):
        # Children are in reading order
        raise NotImplementedError
