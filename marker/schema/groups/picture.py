from marker.schema import BlockTypes
from marker.schema.groups.base import Group


class PictureGroup(Group):
    block_type: BlockTypes = BlockTypes.PictureGroup
