from typing import Optional

from pydantic import BaseModel

from marker.v2.schema import BlockTypes


class BaseRenderer:
    block_type: BlockTypes | None = None

    def __init__(self, config: Optional[BaseModel | dict] = None):
        if config:
            for k in config.model_fields:
                setattr(self, k, config[k])

    def __call__(self, document):
        # Children are in reading order
        raise NotImplementedError
