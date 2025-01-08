from marker.schema import BlockTypes
from marker.schema.blocks.basetable import BaseTable


class Table(BaseTable):
    block_type: BlockTypes = BlockTypes.Table
