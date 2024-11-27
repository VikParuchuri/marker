from marker.schema import BlockTypes
from marker.schema.groups.base import Group


class FigureGroup(Group):
    block_type: BlockTypes = BlockTypes.FigureGroup
