from pydantic import BaseModel


def assign_config(cls, config: BaseModel | dict | None):
    if config is None:
        return
    elif isinstance(config, BaseModel):
        for k in config.model_fields:
            setattr(cls, k, config[k])
    elif isinstance(config, dict):
        for k, v in config.items():
            setattr(cls, k, v)