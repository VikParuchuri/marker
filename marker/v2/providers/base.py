from typing import List

from marker.v2.schema.config.provider import ProviderConfig
from marker.v2.schema.text.line import Line


class BaseProvider:
    def __init__(self, filepath: str, config: ProviderConfig):
        self.filepath = filepath
        self.config = config

        self.setup()

    def __len__(self):
        pass

    def setup(self):
        pass

    def get_image(self, idx: int, dpi: int):
        pass

    def get_page_lines(self, idx: int) -> List[Line]:
        pass
