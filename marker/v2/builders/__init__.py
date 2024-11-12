class BaseBuilder:
    def __init__(self, config):
        self.config = config

    def __call__(self, data, *args, **kwargs):
        raise NotImplementedError
