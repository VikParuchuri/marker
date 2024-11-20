import html

from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class Code(Block):
    block_type: BlockTypes = BlockTypes.Code
    code: str | None = None

    def assemble_html(self, child_blocks, parent_structure):
        code = self.code or ""
        return (f"<pre>"
                f"{html.escape(code)}"
                f"</pre>")
