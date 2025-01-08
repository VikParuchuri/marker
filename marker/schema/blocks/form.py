from typing import List

from marker.schema import BlockTypes
from marker.schema.blocks.basetable import BaseTable


class Form(BaseTable):
    block_type: BlockTypes = BlockTypes.Form
