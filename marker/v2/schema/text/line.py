from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block, BlockOutput


class Line(Block):
    block_type: BlockTypes = BlockTypes.Span

    def assemble_html(self, child_blocks):
        template = ""
        for c in child_blocks:
            template += c.html
        return template

    def render(self, document):
        child_content = []
        if self.structure is not None and len(self.structure) > 0:
            for block_id in self.structure:
                block = document.get_block(block_id)
                child_content.append(block.render(document))

        return BlockOutput(
            html=self.assemble_html(child_content),
            polygon=self.polygon,
            id=self.id,
            children=[]
        )
