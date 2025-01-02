import markdown2

from marker.processors.llm import BaseLLMProcessor

from google.ai.generativelanguage_v1beta.types import content

from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup


class LLMComplexRegionProcessor(BaseLLMProcessor):
    block_types = (BlockTypes.ComplexRegion,)
    gemini_rewriting_prompt = """You are a text correction expert specializing in accurately reproducing text from images.
You will receive an image of a text block and the text that can be extracted from the image.
Your task is to correct any errors in the text, and format it properly.

Formatting should be in markdown, with the following rules:
- * for italics, ** for bold, and ` for inline code.
- Headers should be formatted with #, with one # for the largest header, and up to 6 for the smallest.
- Lists should be formatted with either - or 1. for unordered and ordered lists, respectively.
- Links should be formatted with [text](url).
- Use ``` for code blocks.
- Inline math should be formatted with <math>math expression</math>.
- Display math should be formatted with <math display="block">math expression</math>.
- Values and labels should be extracted from forms, and put into markdown tables, with the labels on the left side, and values on the right.  The headers should be "Labels" and "Values".  Other text in the form can appear between the tables.
- Tables should be formatted with markdown tables, with the headers bolded.

**Instructions:**
1. Carefully examine the provided block image.
2. Analyze the text representation
3. If the text representation is largely correct, then write "No corrections needed."
4. If the text representation contains errors, generate the corrected markdown representation.
5. Output only either the corrected markdown representation or "No corrections needed."
**Example:**
Input:
```text
This is an example text block.
```
Output:
```markdown
No corrections needed.
```
**Input:**
"""

    def process_rewriting(self, document: Document, page: PageGroup, block: Block):
        text = block.raw_text(document)

        prompt = self.gemini_rewriting_prompt + '```text\n`' + text + '`\n```\n'
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

        # Potentially a partial response
        if len(corrected_markdown) < len(text) * .5:
            block.update_metadata(llm_error_count=1)
            return

        # Convert LLM markdown to html
        block.html = markdown2.markdown(corrected_markdown)