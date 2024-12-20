import markdown2

from marker.llm import GoogleModel
from marker.processors import BaseProcessor
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from google.ai.generativelanguage_v1beta.types import content
from tqdm import tqdm
from tabled.formats import markdown_format

from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.settings import settings


class HighQualityFormProcessor(BaseProcessor):
    """
    A processor for converting form blocks in a document to markdown.
    Attributes:
        google_api_key (str):
            The Google API key to use for the Gemini model.
            Default is None.
        model_name (str):
            The name of the Gemini model to use.
            Default is "gemini-1.5-flash".
        max_retries (int):
            The maximum number of retries to use for the Gemini model.
            Default is 3.
        max_concurrency (int):
            The maximum number of concurrent requests to make to the Gemini model.
            Default is 3.
        timeout (int):
            The timeout for requests to the Gemini model.
        gemini_rewriting_prompt (str):
            The prompt to use for rewriting text.
            Default is a string containing the Gemini rewriting prompt.
    """

    block_types = (BlockTypes.Form,)
    google_api_key: Optional[str] = settings.GOOGLE_API_KEY
    model_name: str = "gemini-1.5-flash"
    high_quality: bool = False
    max_retries: int = 3
    max_concurrency: int = 3
    timeout: int = 60

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

    def __init__(self, config=None):
        super().__init__(config)

        self.model = None
        if not self.high_quality:
            return

        self.model = GoogleModel(self.google_api_key, self.model_name)

    def __call__(self, document: Document):
        if not self.high_quality or self.model is None:
            return

        self.rewrite_blocks(document)

    def rewrite_blocks(self, document: Document):
        pbar = tqdm(desc="High quality form processor")
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            for future in as_completed([
                executor.submit(self.process_rewriting, page, block)
                for page in document.pages
                for block in page.contained_blocks(document, self.block_types)
            ]):
                future.result()  # Raise exceptions if any occurred
                pbar.update(1)

        pbar.close()

    def process_rewriting(self, page: PageGroup, block: Block):
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

        orig_cell_text = "".join([cell.text for cell in cells])

        # Potentially a partial response
        if len(corrected_markdown) < len(orig_cell_text) * .5:
            return

        # Convert LLM markdown to html
        block.html = markdown2.markdown(corrected_markdown)

    def extract_image(self, page: PageGroup, image_block: Block, expand: float = 0.01):
        page_img = page.lowres_image
        image_box = image_block.polygon\
            .rescale(page.polygon.size, page_img.size)\
            .expand(expand, expand)
        cropped = page_img.crop(image_box.bbox)
        return cropped