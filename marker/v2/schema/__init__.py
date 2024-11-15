from marker.v2.schema.blocks import Block, LAYOUT_BLOCK_REGISTRY
from marker.v2.schema.groups import GROUP_BLOCK_REGISTRY
from marker.v2.schema.text import TEXT_BLOCK_REGISTRY


class _BlockTypes:
    def __init__(self):
        pass

    def add(self, registry: dict[str, Block]):
        for k, v in registry.items():
            setattr(self, k, k)


BlockTypes = _BlockTypes()
BlockTypes.add(GROUP_BLOCK_REGISTRY)
BlockTypes.add(TEXT_BLOCK_REGISTRY)
BlockTypes.add(LAYOUT_BLOCK_REGISTRY)
