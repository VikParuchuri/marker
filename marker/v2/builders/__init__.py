from typing import Optional

from pydantic import BaseModel


class BaseBuilder:
    def __init__(self, config: Optional[BaseModel] = None):
        if config:
            for k in config.model_fields:
                setattr(self, k, config[k])

    def __call__(self, data, *args, **kwargs):
        raise NotImplementedError
