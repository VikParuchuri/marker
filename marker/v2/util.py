def assign_config(cls, config):
    if config:
        for k in config.model_fields:
            setattr(cls, k, config[k])