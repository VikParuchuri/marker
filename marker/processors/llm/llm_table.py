from tabled.schema import SpanTableCell

from marker.processors.llm import BaseLLMProcessor
from marker.processors.llm.utils import GoogleModel
from marker.processors import BaseProcessor
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List

from google.ai.generativelanguage_v1beta.types import content
from tqdm import tqdm
from tabled.formats import markdown_format

from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.polygon import PolygonBox
from marker.settings import settings


class LLMTableProcessor(BaseLLMProcessor):
    block_types = (BlockTypes.Table,)
    gemini_rewriting_prompt = """You are a text correction expert specializing in accurately reproducing text from images.
You will receive an image of a text block and a markdown representation of the table in the image.
Your task is to correct any errors in the markdown representation.  The markdown representation should be as faithful to the original table as possible.
**Instructions:**
1. Carefully examine the provided text block image.
2. Analyze the markdown representation of the table.
3. If the markdown representation is largely correct, then write "No corrections needed."
4. If the markdown representation contains errors, generate the corrected markdown representation.
5. Output only either the corrected markdown representation or "No corrections needed."
**Example:**
Input:
```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
```
Output:
```markdown
No corrections needed.
```
**Input:**
"""

    def process_rewriting(self, document: Document, page: PageGroup, block: Block):
        cells = block.cells
        if cells is None:
            # Happens if table/form processors didn't run
            return

        prompt = self.gemini_rewriting_prompt + '```markdown\n`' + markdown_format(cells) + '`\n```\n'
        image = self.extract_image(page, block)
        response_schema = content.Schema(
            type=content.Type.OBJECT,
            enum=[],
            required=["corrected_markdown"],
            properties={
                "corrected_markdown": content.Schema(
                    type=content.Type.STRING
                )
            },
        )

        response = self.model.generate_response(prompt, image, response_schema)

        if not response or "corrected_markdown" not in response:
            return

        corrected_markdown = response["corrected_markdown"]

        # The original table is okay
        if "no corrections" in corrected_markdown.lower():
            return

        parsed_cells = self.parse_markdown_table(corrected_markdown, block)
        if len(parsed_cells) <= 1:
            return

        parsed_cell_text = "".join([cell.text for cell in parsed_cells])
        orig_cell_text = "".join([cell.text for cell in cells])

        # Potentially a partial response
        if len(parsed_cell_text) < len(orig_cell_text) * .5:
            return


        block.cells = parsed_cells


    def parse_markdown_table(self, markdown_text: str, block: Block) -> List[SpanTableCell]:
        lines = [line.strip() for line in markdown_text.splitlines() if line.strip()]

        # Remove separator row for headers
        lines = [line for line in lines if not line.replace('|', ' ').replace('-', ' ').isspace()]

        rows = []
        for line in lines:
            # Remove leading/trailing pipes and split by remaining pipes
            cells = line.strip('|').split('|')
            # Clean whitespace from each cell
            cells = [cell.strip() for cell in cells]
            rows.append(cells)

        cells = []
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                cell_bbox = [
                    block.polygon.bbox[0] + j,
                    block.polygon.bbox[1] + i,
                    block.polygon.bbox[0] + j + 1,
                    block.polygon.bbox[1] + i + 1
                ]
                cell_polygon = PolygonBox.from_bbox(cell_bbox)
                cells.append(
                    SpanTableCell(
                        text=cell,
                        row_ids=[i],
                        col_ids=[j],
                        bbox=cell_polygon.bbox
                    )
                )


        return cells
