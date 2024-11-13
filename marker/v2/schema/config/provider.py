from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProviderConfig(BaseModel):
    page_range: Optional[range] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
