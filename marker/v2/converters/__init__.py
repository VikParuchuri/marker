from typing import List

from pydantic import BaseModel


class ConverterConfig(BaseModel):
    filepath: str
    page_range: List[int] | None = None


class BaseConverter:
    def __init__(self, config: ConverterConfig):
        self.config = config

    def __call__(self):
        raise NotImplementedError