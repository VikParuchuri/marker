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


class LLMImageDescriptionProcessor(BaseLLMProcessor):
    block_types = (BlockTypes.Picture, BlockTypes.Figure,)
    extract_images: bool = True
    image_description_prompt = """You are a document analysis expert who specializes in creating text descriptions for images.
You will receive an image of a picture or figure.  Your job will be to create a short description of the image.
**Instructions:**
1. Carefully examine the provided image.
2. Analyze any text that was extracted from within the image.
3. Output a 3-4 sentence description of the image.  Make sure there is enough specific detail to accurately describe the image.  If there are numbers included, try to be specific.
**Example:**
Input:
```text
"Fruit Preference Survey"
20, 15, 10
Apples, Bananas, Oranges
```
Output:
In this figure, a bar chart titled "Fruit Preference Survey" is showing the number of people who prefer different types of fruits.  The x-axis shows the types of fruits, and the y-axis shows the number of people.  The bar chart shows that most people prefer apples, followed by bananas and oranges.  20 people prefer apples, 15 people prefer bananas, and 10 people prefer oranges.
**Input:**
"""

    def process_rewriting(self, document: Document, page: PageGroup, block: Block):
        if self.extract_images:
            # We will only run this processor if we're not extracting images
            # Since this processor replaces images with descriptions
            return

        prompt = self.image_description_prompt + '```text\n`' + block.raw_text(document) + '`\n```\n'
        image = self.extract_image(page, block)
        response_schema = content.Schema(
            type=content.Type.OBJECT,
            enum=[],
            required=["image_description"],
            properties={
                "image_description": content.Schema(
                    type=content.Type.STRING
                )
            },
        )

        response = self.model.generate_response(prompt, image, block, response_schema)

        if not response or "image_description" not in response:
            block.update_metadata(llm_error_count=1)
            return

        image_description = response["image_description"]
        if len(image_description) < 10:
            block.update_metadata(llm_error_count=1)
            return

        block.description = image_description


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
