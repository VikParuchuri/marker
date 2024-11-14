from typing import Optional

from pydantic import BaseModel


class BaseRenderer:
    def __init__(self, config: Optional[BaseModel] = None):
        if config:
            for k in config.model_fields:
                setattr(self, k, config[k])