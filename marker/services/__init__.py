from typing import Optional, List

import PIL
from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.util import assign_config, verify_config_keys


class BaseService:
    def __init__(self, config: Optional[BaseModel | dict] = None):
        assign_config(self, config)

        # Ensure we have all necessary fields filled out (API keys, etc.)
        verify_config_keys(self)

    def __call__(
        self,
        prompt: str,
        image: PIL.Image.Image | List[PIL.Image.Image],
        block: Block,
        response_schema: type[BaseModel],
        max_retries: int = 1,
        timeout: int = 15
     ):
        raise NotImplementedError