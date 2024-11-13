from pydantic import BaseModel, ConfigDict


class ProviderConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
