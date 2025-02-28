from typing import Optional, List, Annotated

import PIL
from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.util import assign_config, verify_config_keys


class BaseService:
    timeout: Annotated[
        int,
        "The timeout to use for the service."
    ] = 30
    max_retries: Annotated[
        int,
        "The maximum number of retries to use for the service."
    ] = 2

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
        max_retries: int | None = None,
        timeout: int | None = None
     ):
        raise NotImplementedError