from tabled.schema import SpanTableCell

from marker.processors.llm import BaseLLMProcessor
from bs4 import BeautifulSoup
from typing import List

from google.ai.generativelanguage_v1beta.types import content
from tabled.formats import html_format

from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.polygon import PolygonBox


class LLMTableProcessor(BaseLLMProcessor):
    block_types = (BlockTypes.Table,)
    gemini_rewriting_prompt = """You are a text correction expert specializing in accurately reproducing text from images.
You will receive an image of a text block and an html representation of the table in the image.
Your task is to correct any errors in the html representation.  The html representation should be as faithful to the original table as possible.
**Instructions:**
1. Carefully examine the provided text block image.
2. Analyze the html representation of the table.
3. If the html representation is largely correct, then write "No corrections needed."
4. If the html representation contains errors, generate the corrected html representation.  Only use the tags th, td, tr, and table.  Only use the attributes colspan and rowspan if necessary.
5. Output only either the corrected html representation or "No corrections needed."
**Example:**
Input:
```html
<table>
    <tr>
        <th>First Name</th>
        <th>Last Name</th>
        <th>Age</th>
    </tr>
    <tr>
        <td>John</td>
        <td>Doe</td>
        <td>25</td>
    </tr>
</table>
```
Output:
```html
No corrections needed.
```
**Input:**
"""

    def process_rewriting(self, document: Document, page: PageGroup, block: Block):
        cells = block.cells
        if cells is None:
            # Happens if table/form processors didn't run
            return

        prompt = self.gemini_rewriting_prompt + '```html\n`' + html_format(cells) + '`\n```\n'
        image = self.extract_image(page, block)
        response_schema = content.Schema(
            type=content.Type.OBJECT,
            enum=[],
            required=["corrected_html"],
            properties={
                "corrected_html": content.Schema(
                    type=content.Type.STRING
                )
            },
        )

        response = self.model.generate_response(prompt, image, block, response_schema)

        if not response or "corrected_html" not in response:
            block.update_metadata(llm_error_count=1)
            return

        corrected_html = response["corrected_html"]

        # The original table is okay
        if "no corrections" in corrected_html.lower():
            return

        parsed_cells = self.parse_html_table(corrected_html, block)
        if len(parsed_cells) <= 1:
            block.update_metadata(llm_error_count=1)
            return

        parsed_cell_text = "".join([cell.text for cell in parsed_cells])
        orig_cell_text = "".join([cell.text for cell in cells])

        # Potentially a partial response
        if len(parsed_cell_text) < len(orig_cell_text) * .5:
            block.update_metadata(llm_error_count=1)
            return


        block.cells = parsed_cells


    def parse_html_table(self, html_text: str, block: Block) -> List[SpanTableCell]:
        soup = BeautifulSoup(html_text, 'html.parser')
        table = soup.find('table')

        # Initialize grid
        rows = table.find_all('tr')
        cells = []
        max_cols = max(len(row.find_all(['td', 'th'])) for row in rows)
        if max_cols == 0:
            return []

        grid = [[True] * max_cols for _ in range(len(rows))]

        for i, row in enumerate(rows):
            cur_col = 0
            row_cells = row.find_all(['td', 'th'])
            for j, cell in enumerate(row_cells):
                while cur_col < max_cols and not grid[i][cur_col]:
                    cur_col += 1

                if cur_col >= max_cols:
                    print("Table parsing warning: too many columns found")
                    break

                cell_text = cell.text.strip()
                rowspan = min(int(cell.get('rowspan', 1)), len(rows) - i)
                colspan = min(int(cell.get('colspan', 1)), max_cols - cur_col)
                cell_rows = list(range(i, i + rowspan))
                cell_cols = list(range(cur_col, cur_col + colspan))

                if colspan == 0 or rowspan == 0:
                    print("Table parsing warning: invalid colspan or rowspan")
                    continue

                for r in cell_rows:
                    for c in cell_cols:
                        grid[r][c] = False

                cell_bbox = [
                    block.polygon.bbox[0] + cur_col,
                    block.polygon.bbox[1] + i,
                    block.polygon.bbox[0] + cur_col + colspan,
                    block.polygon.bbox[1] + i + rowspan
                ]
                cell_polygon = PolygonBox.from_bbox(cell_bbox)

                cell_obj = SpanTableCell(
                    text=cell_text,
                    row_ids=cell_rows,
                    col_ids=cell_cols,
                    bbox=cell_polygon.bbox
                )
                cells.append(cell_obj)
                cur_col += colspan


        return cells
