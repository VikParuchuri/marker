from pydantic import BaseModel


class ProviderConfig(BaseModel):
    share_model_memory: bool = False
    model_device: str = "cpu"
    batch_size: int = 1