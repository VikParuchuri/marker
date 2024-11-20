from marker.v2.processors import BaseProcessor
from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Code
from marker.v2.schema.document import Document


class CodeProcessor(BaseProcessor):
    block_types = (BlockTypes.Code, )
    y_top_threshold = 2 # pixels

    def __call__(self, document: Document):
        for page in document.pages:
            for block in page.children:
                if block.block_type not in self.block_types:
                    continue
                self.format_block(document, block)

    def format_block(self, document: Document, block: Code):
        min_left = 9999  # will contain x- coord of column 0
        total_width = 0
        total_chars = 0
        for line_id in block.structure:
            line = document.get_block(line_id)
            min_left = min(line.polygon.bbox[0], min_left)
            total_width += line.polygon.width
            total_chars += len(line.raw_text(document))

        avg_char_width = total_width / max(total_chars, 1)
        code_text = ""
        is_new_line = False
        for line_id in block.structure:
            line = document.get_block(line_id)
            text = line.raw_text(document)
            if avg_char_width == 0:
                prefix = ""
            else:
                total_spaces = int((line.polygon.bbox[0] - min_left) / avg_char_width)
                prefix = " " * max(0, total_spaces)

            if is_new_line:
                text = prefix + text

            code_text += text
            is_new_line = text.endswith("\n")

        block.code = code_text
