from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Molecule(Block):
    block_type: BlockTypes = BlockTypes.Molecule
    block_description: str = "A chemical molecule structure or formula."
    html: str | None = None
    replace_output_newlines: bool = True
    structure_data: dict = {}
    confidence: float = 1.0
    
    def assemble_html(self, document, child_blocks, parent_structure):
        # 如果是mock数据，输出固定内容
        if self.structure_data.get('mock', False):
            return "<p>c1ccccc1</p>"
        
        # 如果有自定义html
        if self.html:
            return f"<p>{self.html}</p>"
        
        # 如果有结构数据中的内容
        if self.structure_data.get('content'):
            return f"<p>{self.structure_data['content']}</p>"
        
        # 如果有SMILES数据
        if self.structure_data.get('smiles'):
            return f"<p>{self.structure_data['smiles']}</p>"
        
        # 默认使用基类的内容
        return f"<p>{super().assemble_html(document, child_blocks, parent_structure)}</p>"


class MoleculeTable(Block):
    block_type: BlockTypes = BlockTypes.MoleculeTable
    block_description: str = "A table containing chemical molecules or molecular data."
    html: str | None = None
    replace_output_newlines: bool = True
    table_data: dict = {}
    confidence: float = 1.0
    
    def assemble_html(self, document, child_blocks, parent_structure):
        # 如果是mock数据，输出固定内容
        if self.table_data.get('mock', False):
            return "<table>placeholder</table>"
        
        # 如果有自定义html
        if self.html:
            return f"{self.html}"
        
        # 如果有表格数据中的内容
        if self.table_data.get('content'):
            return f"<table>{self.table_data['content']}</table>"
        
        # 默认使用基类的内容
        return f"<table>{super().assemble_html(document, child_blocks, parent_structure)}</table>" 