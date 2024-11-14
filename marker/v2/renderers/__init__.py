from typing import Optional

from pydantic import BaseModel


class BaseRenderer:
    block_type: str | None = None
    
    def __init__(self, config: Optional[BaseModel | dict] = None):
        if config:
            for k in config.model_fields:
                setattr(self, k, config[k])