from typing import Annotated, List, Tuple

from bs4 import BeautifulSoup
from google.ai.generativelanguage_v1beta.types import content
from PIL import Image

from marker.processors.llm import BaseLLMProcessor
from marker.schema import BlockTypes
from marker.schema.blocks import Block, TableCell, Table
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.polygon import PolygonBox


class LLMTableProcessor(BaseLLMProcessor):
    block_types: Annotated[
        Tuple[BlockTypes],
        "The block types to process.",
    ] = (BlockTypes.Table, BlockTypes.TableOfContents)
    max_rows_per_batch: Annotated[
        int,
        "If the table has more rows than this, chunk the table. (LLMs can be inaccurate with a lot of rows)",
    ] = 60
    max_table_rows: Annotated[
        int,
        "The maximum number of rows in a table to process with the LLM processor.  Beyond this will be skipped.",
    ] = 175
    table_image_expansion_ratio: Annotated[
        float,
        "The ratio to expand the image by when cropping.",
    ] = 0
    table_rewriting_prompt: Annotated[
        str,
        "The prompt to use for rewriting text.",
        "Default is a string containing the Gemini rewriting prompt."
    ] = """You are a text correction expert specializing in accurately reproducing text from images.
You will receive an image of a text block and an html representation of the table in the image.
Your task is to correct any errors in the html representation.  The html representation should be as faithful to the original table as possible.

Some guidelines:
- Make sure to reproduce the original values as faithfully as possible.
- If you see any math in a table cell, fence it with the <math display="inline"> tag.  Block math should be fenced with <math display="block">.
- Replace any images with a description, like "Image: [description]".
- Only use the tags th, td, tr, br, span, i, b, math, and table.  Only use the attributes display, style, colspan, and rowspan if necessary.  You can use br to break up text lines in cells.

**Instructions:**
1. Carefully examine the provided text block image.
2. Analyze the html representation of the table.
3. If the html representation is largely correct, or you cannot read the image properly, then write "No corrections needed."
4. If the html representation contains errors, generate the corrected html representation.  
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
```html
{block_html}
```
"""

    def process_rewriting(self, document: Document, page: PageGroup, block: Table):
        children: List[TableCell] = block.contained_blocks(document, (BlockTypes.TableCell,))
        if not children:
            # Happens if table/form processors didn't run
            return

        # LLMs don't handle tables with a lot of rows very well
        unique_rows = set([cell.row_id for cell in children])
        row_count = len(unique_rows)
        row_idxs = sorted(list(unique_rows))

        if row_count > self.max_table_rows:
            return

        # Inference by chunk to handle long tables better
        parsed_cells = []
        row_shift = 0
        block_image = self.extract_image(document, block)
        block_rescaled_bbox = block.polygon.rescale(page.polygon.size, page.get_image(highres=True).size).bbox
        for i in range(0, row_count, self.max_rows_per_batch):
            batch_row_idxs = row_idxs[i:i + self.max_rows_per_batch]
            batch_cells = [cell for cell in children if cell.row_id in batch_row_idxs]
            batch_cell_bboxes = [cell.polygon.rescale(page.polygon.size, page.get_image(highres=True).size).bbox for cell in batch_cells]
            # bbox relative to the block
            batch_bbox = [
                min([bbox[0] for bbox in batch_cell_bboxes]) - block_rescaled_bbox[0],
                min([bbox[1] for bbox in batch_cell_bboxes]) - block_rescaled_bbox[1],
                max([bbox[2] for bbox in batch_cell_bboxes]) - block_rescaled_bbox[0],
                max([bbox[3] for bbox in batch_cell_bboxes]) - block_rescaled_bbox[1]
            ]
            if i == 0:
                # Ensure first image starts from the beginning
                batch_bbox[0] = 0
                batch_bbox[1] = 0
            elif i > row_count - self.max_rows_per_batch + 1:
                # Ensure final image grabs the entire height and width
                batch_bbox[2] = block_image.size[0]
                batch_bbox[3] = block_image.size[1]

            batch_image = block_image.crop(batch_bbox)
            block_html = block.format_cells(document, [], batch_cells)
            batch_parsed_cells = self.rewrite_single_chunk(page, block, block_html, batch_cells, batch_image)
            if batch_parsed_cells is None:
                return # Error occurred or no corrections needed

            for cell in batch_parsed_cells:
                cell.row_id += row_shift
                parsed_cells.append(cell)
            row_shift += max([cell.row_id for cell in batch_parsed_cells])

        block.structure = []
        for cell in parsed_cells:
            page.add_full_block(cell)
            block.add_structure(cell)

    def rewrite_single_chunk(self, page: PageGroup, block: Block, block_html: str, children: List[TableCell], image: Image.Image):
        prompt = self.table_rewriting_prompt.replace("{block_html}", block_html)

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

        corrected_html = corrected_html.strip().lstrip("```html").rstrip("```").strip()
        parsed_cells = self.parse_html_table(corrected_html, block, page)
        if len(parsed_cells) <= 1:
            block.update_metadata(llm_error_count=1)
            return

        parsed_cell_text = "".join([cell.text for cell in parsed_cells])
        orig_cell_text = "".join([cell.text for cell in children])
        # Potentially a partial response
        if len(parsed_cell_text) < len(orig_cell_text) * .5:
            block.update_metadata(llm_error_count=1)
            return

        return parsed_cells

    @staticmethod
    def get_cell_text(element, keep_tags=('br','i', 'b', 'span', 'math')) -> str:
        for tag in element.find_all(True):
            if tag.name not in keep_tags:
                tag.unwrap()
        return element.decode_contents()

    def parse_html_table(self, html_text: str, block: Block, page: PageGroup) -> List[TableCell]:
        soup = BeautifulSoup(html_text, 'html.parser')
        table = soup.find('table')

        # Initialize grid
        rows = table.find_all('tr')
        cells = []

        # Find maximum number of columns in colspan-aware way
        max_cols = 0
        for row in rows:
            row_tds = row.find_all(['td', 'th'])
            curr_cols = 0
            for cell in row_tds:
                colspan = int(cell.get('colspan', 1))
                curr_cols += colspan
            if curr_cols > max_cols:
                max_cols = curr_cols

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

                cell_text = self.get_cell_text(cell).strip()
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

                cell_obj = TableCell(
                    text_lines=[cell_text],
                    row_id=i,
                    col_id=cur_col,
                    rowspan=rowspan,
                    colspan=colspan,
                    is_header=cell.name == 'th',
                    polygon=cell_polygon,
                    page_id=page.page_id,
                )
                cells.append(cell_obj)
                cur_col += colspan

        return cells
