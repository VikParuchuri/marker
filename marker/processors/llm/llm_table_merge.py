from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated, List, Tuple, Literal

from google.ai.generativelanguage_v1beta.types import content
from tqdm import tqdm
from PIL import Image

from marker.processors.llm import BaseLLMProcessor
from marker.schema import BlockTypes
from marker.schema.blocks import Block, TableCell
from marker.schema.document import Document


class LLMTableMergeProcessor(BaseLLMProcessor):
    block_types: Annotated[
        Tuple[BlockTypes],
        "The block types to process.",
    ] = (BlockTypes.Table, BlockTypes.TableOfContents)
    table_height_threshold: Annotated[
        float,
        "The minimum height ratio relative to the page for the first table in a pair to be considered for merging.",
    ] = 0.6
    table_start_threshold: Annotated[
        float,
        "The maximum percentage down the page the second table can start to be considered for merging."
    ] = 0.2
    vertical_table_height_threshold: Annotated[
        float,
        "The height tolerance for 2 adjacent tables to be merged into one."
    ] = 0.25
    vertical_table_distance_threshold: Annotated[
        int,
        "The maximum distance between table edges for adjacency."
    ] = 20
    gemini_table_merge_prompt: Annotated[
        str,
        "The prompt to use for rewriting text.",
        "Default is a string containing the Gemini rewriting prompt."
    ] = """You're a text correction expert specializing in accurately reproducing tables from PDFs.
You'll receive two images of tables from successive pages of a PDF.  Table 1 is from the first page, and Table 2 is from the second page.  Both tables may actually be part of the same larger table. Your job is to decide if Table 2 should be merged with Table 1, and how they should be joined.  The should only be merged if they're both part of the same larger table, and Table 2 cannot be interpreted without merging.

You'll specify your judgement in json format - first whether Table 2 should be merged with Table 1, then the direction of the merge, either bottom or right.  Table 2 should be merged at the bottom of Table 1 if Table 2 has no headers, and the rows have similar values, meaning that Table 2 continues Table 1. Table2  should be merged to the right of Table 1 if each row in Table 2 matches a row in Table 1, meaning that Table 2 contains additional columns from Table 1.

In general, you should only merge Table 1 and Table 2 if Table 2 cannot effectively be interpreted without merging.
**Instructions:**
1. Carefully examine the provided table images.  Table 1 is the first image, and Table 2 is the second image.
2. Examine the provided html representations of Table 1 and Table 2.
3. Write a description of Table 1.
4. Write a description of Table 2.
5. Analyze whether Table 2 should be merged into Table 1, and write an explanation.
6. Output your decision on whether they should be merged, and merge direction.
**Example:**
Input:
Table 1
```html
<table>
    <tr>
        <th>Name</th>
        <th>Age</th>
        <th>City</th>
        <th>State</th>
    </tr>
    <tr>
        <td>John</td>
        <td>25</td>
        <td>Chicago</td>
        <td>IL</td>
    </tr>
```
Table 2
```html
<table>
    <tr>
        <th>Name</th>
        <th>Age</th>
        <th>City</th>
        <th>State</th>
    </tr>
    <tr>
        <td>Jane</td>
        <td>30</td>
        <td>Los Angeles</td>
        <td>CA</td>
    </tr>
```
Output:
```json
{
    "table1_description": "The first table has 4 headers, and 1 row.  The headers are Name, Age, City, and State.",
    "table2_description": "The second table has 4 headers, and 1 row.  The headers are Name, Age, City, and State.",
    "explanation": "The tables should be merged, as they have the same headers.  The second table should be merged to the bottom of the first table.",
    "merge": "true",
    "direction": "bottom"
}
```
**Input:**
Table 1
```html
{{table1}}
Table 2
```html
{{table2}}
```
"""

    def rewrite_blocks(self, document: Document):
        pbar = tqdm(desc=f"{self.__class__.__name__} running")
        table_runs = []
        table_run = []
        prev_block = None
        prev_page_block_count = None
        for page in document.pages:
            page_blocks = page.contained_blocks(document, self.block_types)
            for block in page_blocks:
                if prev_block is None:
                    subsequent_page_table = False
                    same_page_vertical_table = False
                else:
                    subsequent_page_table = all([
                        prev_block.page_id == block.page_id - 1, # Subsequent pages
                        max(prev_block.polygon.height / page.polygon.height,
                            block.polygon.height / page.polygon.height) > self.table_height_threshold, # Take up most of the page height
                            (len(page_blocks) == 1 or prev_page_block_count == 1) # Only table on the page
                        ])

                    same_page_vertical_table = all([
                        prev_block.page_id == block.page_id, # On the same page
                        (1 - self.vertical_table_height_threshold) < prev_block.polygon.height / block.polygon.height < (1 + self.vertical_table_height_threshold), # Similar height
                        abs(block.polygon.x_start - prev_block.polygon.x_end) < self.vertical_table_distance_threshold, # Close together in x
                    ])

                if prev_block is not None and \
                        (subsequent_page_table or same_page_vertical_table):
                    if prev_block not in table_run:
                        table_run.append(prev_block)
                    table_run.append(block)
                else:
                    if table_run:
                        table_runs.append(table_run)
                    table_run = []
                prev_block = block
            prev_page_block_count = len(page_blocks)

        if table_run:
            table_runs.append(table_run)

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            for future in as_completed([
                executor.submit(self.process_rewriting, document, blocks)
                for blocks in table_runs
            ]):
                future.result()  # Raise exceptions if any occurred
                pbar.update(1)

        pbar.close()

    def process_rewriting(self, document: Document, blocks: List[Block]):
        if len(blocks) < 2:
            # Can't merge single tables
            return

        start_block = blocks[0]
        for i in range(1, len(blocks)):
            curr_block = blocks[i]
            children = start_block.contained_blocks(document, (BlockTypes.TableCell,))
            children_curr = curr_block.contained_blocks(document, (BlockTypes.TableCell,))
            if not children or not children_curr:
                # Happens if table/form processors didn't run
                continue

            start_image = start_block.get_image(document, highres=False)
            curr_image = curr_block.get_image(document, highres=False)
            start_html = start_block.render(document).html
            curr_html = curr_block.render(document).html

            prompt = self.gemini_table_merge_prompt.replace("{{table1}}", start_html).replace("{{table2}}", curr_html)

            response_schema = content.Schema(
                type=content.Type.OBJECT,
                enum=[],
                required=["table1_description", "table2_description", "explanation", "merge", "direction"],
                properties={
                    "table1_description": content.Schema(
                        type=content.Type.STRING
                    ),
                    "table2_description": content.Schema(
                        type=content.Type.STRING
                    ),
                    "explanation": content.Schema(
                        type=content.Type.STRING
                    ),
                    "merge": content.Schema(
                        type=content.Type.STRING,
                        enum=["true", "false"]
                    ),
                    "direction": content.Schema(
                        type=content.Type.STRING,
                        enum=["bottom", "right"]
                    ),
                },
            )

            response = self.model.generate_response(
                prompt,
                [start_image, curr_image],
                curr_block,
                response_schema
            )

            if not response or ("direction" not in response or "merge" not in response):
                curr_block.update_metadata(llm_error_count=1)
                return

            merge = response["merge"]

            # The original table is okay
            if "true" not in merge:
                start_block = curr_block
                continue

            # Merge the cells and images of the tables
            direction = response["direction"]
            merged_image = self.join_images(start_image, curr_image, direction)
            merged_cells = self.join_cells(children, children_curr, direction)
            curr_block.structure = []
            start_block.structure = [b.id for b in merged_cells]
            start_block.lowres_image = merged_image

    @staticmethod
    def join_cells(cells1: List[TableCell], cells2: List[TableCell], direction: Literal['right', 'bottom'] = 'right') -> List[TableCell]:
        if direction == 'right':
            new_cells = cells1 + cells2
        else:
            # Shift rows up
            row_count = len(cells1)
            for cell in cells2:
                cell.row_id += row_count
            new_cells = cells1 + cells2
        return new_cells

    @staticmethod
    def join_images(image1: Image.Image, image2: Image.Image, direction: Literal['right', 'bottom'] = 'right') -> Image.Image:
        # Get dimensions
        w1, h1 = image1.size
        w2, h2 = image2.size

        if direction == 'right':
            new_height = max(h1, h2)
            new_width = w1 + w2
            new_img = Image.new('RGB', (new_width, new_height), 'white')
            new_img.paste(image1, (0, 0))
            new_img.paste(image2, (w1, 0))
        else:
            new_width = max(w1, w2)
            new_height = h1 + h2
            new_img = Image.new('RGB', (new_width, new_height), 'white')
            new_img.paste(image1, (0, 0))
            new_img.paste(image2, (0, h1))
        return new_img