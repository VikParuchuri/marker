from typing import Optional

from pydantic import BaseModel

from marker.v2.processors import BaseProcessor


class EquationProcessor(BaseProcessor):
    block_type = "Equation"

    def __init__(self, texify_model, config: Optional[BaseModel] = None):
        super().__init__(config)

        self.texify_model = texify_model

