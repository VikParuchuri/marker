from marker.processors.llm import BaseLLMProcessor

from google.ai.generativelanguage_v1beta.types import content

from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup


class LLMFormProcessor(BaseLLMProcessor):
    block_types = (BlockTypes.Form,)
    form_rewriting_prompt = """You are a text correction expert specializing in accurately reproducing text from images.
You will receive an image of a text block and an html representation of the form in the image.
Your task is to correct any errors in the html representation, and format it properly.
Values and labels should appear in html tables, with the labels on the left side, and values on the right.  The headers should be "Labels" and "Values".  Other text in the form can appear between the tables.  Only use the tags `table, p, span, i, b, th, td, tr, and div`.  Do not omit any text from the form - make sure everything is included in the html representation.  It should be as faithful to the original form as possible.
**Instructions:**
1. Carefully examine the provided form block image.
2. Analyze the html representation of the form.
3. If the html representation is largely correct, or you cannot read the image properly, then write "No corrections needed."
4. If the html representation contains errors, generate the corrected html representation.
5. Output only either the corrected html representation or "No corrections needed."
**Example:**
Input:
```html
<table>
    <tr>
        <td>Label 1</td>
        <td>Label 2</td>
        <td>Label 3</td>
    </tr>
    <tr>
        <td>Value 1</td>
        <td>Value 2</td>
        <td>Value 3</td>
    </tr>
</table> 
```
Output:
```html
<table>
    <tr>
        <th>Labels</th>
        <th>Values</th>
    </tr>
    <tr>
        <td>Label 1</td>
        <td>Value 1</td>
    </tr>
    <tr>
        <td>Label 2</td>
        <td>Value 2</td>
    </tr>
    <tr>
        <td>Label 3</td>
        <td>Value 3</td>
    </tr>
</table>
```
**Input:**
```html
{block_html}
```
"""

    def process_rewriting(self, document: Document, page: PageGroup, block: Block):
        children = block.contained_blocks(document, (BlockTypes.TableCell,))
        if not children:
            # Happens if table/form processors didn't run
            return

        block_html = block.render(document).html
        prompt = self.form_rewriting_prompt.replace("{block_html}", block_html)

        image = self.extract_image(document, block)
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

        # Potentially a partial response
        if len(corrected_html) < len(block_html) * .33:
            block.update_metadata(llm_error_count=1)
            return

        corrected_html = corrected_html.strip().lstrip("```html").rstrip("```").strip()
        block.html = corrected_html