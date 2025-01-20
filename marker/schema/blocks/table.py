from marker.schema import BlockTypes
from marker.schema.blocks.basetable import BaseTable


class Table(BaseTable):
    block_type: BlockTypes = BlockTypes.Table
    block_description: str = "A table of data, like a results table.  It will be in a tabular format."
