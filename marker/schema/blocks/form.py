from typing import List

from marker.schema import BlockTypes
from marker.schema.blocks.basetable import BaseTable


class Form(BaseTable):
    block_type: BlockTypes = BlockTypes.Form
    block_description: str = "A form, such as a tax form, that contains fields and labels.  It most likely doesn't have a table structure."
