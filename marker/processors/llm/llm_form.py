import markdown2

from marker.processors.llm import BaseLLMProcessor

from google.ai.generativelanguage_v1beta.types import content
from tabled.formats import markdown_format

from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup


class LLMFormProcessor(BaseLLMProcessor):
    block_types = (BlockTypes.Form,)
    gemini_rewriting_prompt = """You are a text correction expert specializing in accurately reproducing text from images.
You will receive an image of a text block and a markdown representation of the form in the image.
Your task is to correct any errors in the markdown representation, and format it properly.
Values and labels should appear in markdown tables, with the labels on the left side, and values on the right.  The headers should be "Labels" and "Values".  Other text in the form can appear between the tables.
**Instructions:**
1. Carefully examine the provided form block image.
2. Analyze the markdown representation of the form.
3. If the markdown representation is largely correct, then write "No corrections needed."
4. If the markdown representation contains errors, generate the corrected markdown representation.
5. Output only either the corrected markdown representation or "No corrections needed."
**Example:**
Input:
```markdown
| Label 1 | Label 2 | Label 3 |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
```
Output:
```markdown
| Labels | Values |
|--------|--------|
| Label 1 | Value 1 |
| Label 2 | Value 2 |
| Label 3 | Value 3 |
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

        response = self.model.generate_response(prompt, image, block, response_schema)

        if not response or "corrected_markdown" not in response:
            block.update_metadata(llm_error_count=1)
            return

        corrected_markdown = response["corrected_markdown"]

        # The original table is okay
        if "no corrections" in corrected_markdown.lower():
            return

        orig_cell_text = "".join([cell.text for cell in cells])

        # Potentially a partial response
        if len(corrected_markdown) < len(orig_cell_text) * .5:
            block.update_metadata(llm_error_count=1)
            return

        # Convert LLM markdown to html
        block.html = markdown2.markdown(corrected_markdown)