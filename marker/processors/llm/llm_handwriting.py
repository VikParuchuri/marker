import markdown2

from marker.processors.llm import BaseLLMProcessor

from google.ai.generativelanguage_v1beta.types import content

from marker.schema import BlockTypes
from marker.schema.blocks import Handwriting, Text
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup

from typing import Annotated


class LLMHandwritingProcessor(BaseLLMProcessor):
    block_types = (BlockTypes.Handwriting, BlockTypes.Text)
    handwriting_generation_prompt: Annotated[
        str,
        "The prompt to use for OCRing handwriting.",
        "Default is a string containing the Gemini prompt."
    ] = """You are an expert editor specializing in accurately reproducing text from images.
You will receive an image of a text block. Your task is to generate markdown to properly represent the content of the image.  Do not omit any text present in the image - make sure everything is included in the markdown representation.  The markdown representation should be as faithful to the original image as possible.

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
2. Output the markdown representing the content of the image.
"""

    def process_rewriting(self, document: Document, page: PageGroup, block: Handwriting | Text):
        raw_text = block.raw_text(document)

        # Don't process text blocks that contain lines already
        if block.block_type == BlockTypes.Text:
            lines = block.contained_blocks(document, (BlockTypes.Line,))
            if len(lines) > 0 or len(raw_text.strip()) > 0:
                return

        prompt = self.handwriting_generation_prompt

        image = self.extract_image(document, block)
        response_schema = content.Schema(
            type=content.Type.OBJECT,
            enum=[],
            required=["markdown"],
            properties={
                "markdown": content.Schema(
                    type=content.Type.STRING
                )
            },
        )

        response = self.model.generate_response(prompt, image, block, response_schema)

        if not response or "markdown" not in response:
            block.update_metadata(llm_error_count=1)
            return

        markdown = response["markdown"]
        if len(markdown) < len(raw_text) * .5:
            block.update_metadata(llm_error_count=1)
            return

        markdown = markdown.strip().lstrip("```markdown").rstrip("```").strip()
        block.html = markdown2.markdown(markdown)
