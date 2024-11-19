from marker.v2.schema import BlockTypes
from marker.v2.schema.groups.base import Group


class PictureGroup(Group):
    block_type: BlockTypes = BlockTypes.PictureGroup
