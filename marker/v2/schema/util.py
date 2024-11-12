from marker.v2.schema import Block


def build_block_registry():
    return {
        v.block_type: v for k, v in locals().items()
        if isinstance(v, type)
        and issubclass(v, Block)
        and v != Block  # Exclude the base Block class
    }