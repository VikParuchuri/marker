from marker.v2.schema.blocks.base import Block
from marker.v2.schema.groups.figure import FigureGroup
from marker.v2.schema.groups.table import TableGroup
from marker.v2.schema.groups.list import ListGroup
from marker.v2.schema.groups.picture import PictureGroup
from marker.v2.schema.groups.page import PageGroup

GROUP_BLOCK_REGISTRY = {
    v.model_fields['block_type'].default: v for k, v in locals().items()
    if isinstance(v, type)
    and issubclass(v, Block)
    and v != Block  # Exclude the base Block class
    and (v.model_fields['block_type'].default.endswith("Group") or v.model_fields['block_type'].default == "Page")
}

