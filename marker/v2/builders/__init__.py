class BaseBuilder:
    def __init__(self, config=None):
        if config:
            for k in config:
                setattr(self, k, config[k])

    def __call__(self, data, *args, **kwargs):
        raise NotImplementedError
