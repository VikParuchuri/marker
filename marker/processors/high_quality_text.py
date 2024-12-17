from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import google.generativeai as genai
import PIL
from google.ai.generativelanguage_v1beta.types import content
from google.api_core.exceptions import ResourceExhausted
from tqdm import tqdm

from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.registry import get_block_class
from marker.schema.text.span import Span
from marker.settings import settings


class HighQualityTextProcessor(BaseProcessor):
    """
    A processor for rewriting text to improve the quality of inline math and handwritten blocks.
    Attributes:
        google_api_key (str):
            The Google API key to use for the Gemini model.
            Default is None.
        confidence_threshold (float):
            The confidence threshold to use for relabeling.
            Default is 0.8.
        model_name (str):
            The name of the Gemini model to use.
            Default is "gemini-1.5-flash".
    """

    block_types = (BlockTypes.TextInlineMath, BlockTypes.Handwriting)
    google_api_key: Optional[str] = settings.GOOGLE_API_KEY
    confidence_threshold: float = 0.7
    model_name: str = "gemini-1.5-flash"

    gemini_rewriting_prompt = """You are a text correction expert specializing in accurately reproducing text from images.
You will receive an image of a text block and a set of extracted lines corresponding to the text in the image.
Your task is to correct any errors in the extracted lines, including math, formatting, and other inaccuracies, and output the corrected lines in a JSON format.
The number of output lines MUST match the number of input lines.

**Instructions:**

1. Carefully examine the provided text block image .
2. Analyze the extracted lines.
3. For each extracted line, compare it to the corresponding line in the image.
4. Correct any errors in the extracted line, including:
    * Inline math: Ensure all mathematical expressions are correctly formatted and rendered.
    * Formatting: Maintain consistent formatting with the text block image, including spacing, indentation, and special characters.
    * Other inaccuracies:  If the image is handwritten then you may correct any spelling errors, or other discrepancies.
5. Do not remove any formatting i.e bold, italics, etc from the extracted lines unless it is necessary to correct the error.
6. Ensure that inline math is properly enclosed in dollar signs.
7. The number of corrected lines in the output MUST equal the number of extracted lines provided in the input. Do not add or remove lines.
8. Output the corrected lines in JSON format with a "lines" field, as shown in the example below.

**Example:**

Input:
```
{
 "extracted_lines": [
  "Adversarial training (AT) [23], which aims to minimize\n",
  "the model's risk under the worst-case perturbations, is cur-\n",
  "rently the most effective approach for improving the robust-\n",
  "ness of deep neural networks. For a given neural network\n",
  "f(x, w) with parameters w, the optimization objective of\n",
  "AT can be formulated as follows:\n"
 ]
}
```

Output:

```json
{
 "corrected_lines": [
  "Adversarial training (AT) [23], which aims to minimize\n",
  "the model's risk under the worst-case perturbations, is cur-\n",
  "rently the most effective approach for improving the robust-\n",
  "ness of deep neural networks. For a given neural network\n",
  "$f(x, w)$ with parameters $w$, the optimization objective of\n",
  "AT can be formulated as follows:\n"
 ]
}
```

**Input:**

"""

    def __init__(self, config=None):
        super().__init__(config)

        if self.google_api_key is not None:
            genai.configure(api_key=self.google_api_key)
            self.model = genai.GenerativeModel(self.model_name)

    def __call__(self, document: Document):
        if self.model is None:
            return

        self.rewrite_blocks(document)

    def rewrite_blocks(self, document: Document):
        pbar = tqdm(desc="High quality text processor")
        with ThreadPoolExecutor() as executor:
            for future in as_completed([
                executor.submit(self.process_block_rewriting, document, page, block)
                for page in document.pages
                for block in page.contained_blocks(document, (BlockTypes.TextInlineMath, BlockTypes.Handwriting))
            ]):
                future.result()  # Raise exceptions if any occurred
                pbar.update(1)

        pbar.close()

    def process_block_rewriting(self, document: Document, page: PageGroup, block: Block):
        SpanClass: Span = get_block_class(BlockTypes.Span)

        text_lines = block.contained_blocks(document, (BlockTypes.Line,))
        extracted_lines = [line.formatted_text(document) for line in text_lines]

        prompt = self.gemini_rewriting_prompt + '```json\n`' + json.dumps({"extracted_lines": extracted_lines}, indent=2) + '`\n```\n'
        image = self.extract_image(page, block)
        response_schema = content.Schema(
            type=content.Type.OBJECT,
            enum=[],
            required=["corrected_lines"],
            properties={
                "corrected_lines": content.Schema(
                    type=content.Type.ARRAY,
                    items=content.Schema(
                        type=content.Type.STRING,
                    ),
                )
            },
        )

        response = self.generate(prompt, image, response_schema)
        corrected_lines = []
        if response and "corrected_lines" in response:
            corrected_lines = response["corrected_lines"]

        if corrected_lines and len(corrected_lines) == len(extracted_lines):
            for text_line, corrected_text in zip(text_lines, corrected_lines):
                span_block = page.add_full_block(
                    SpanClass(
                        polygon=text_line.polygon,
                        text=corrected_text + "\n",
                        font='Unknown',
                        font_weight=0,
                        font_size=0,
                        minimum_position=0,
                        maximum_position=0,
                        formats=['plain', 'math'],
                        page_id=text_line.page_id,
                        text_extraction_method="gemini",
                    )
                )
                text_line.structure = [span_block.id]

    def extract_image(self, page: PageGroup, image_block: Block, expand: float = 0.01):
        page_img = page.lowres_image
        image_box = image_block.polygon\
            .rescale(page.polygon.size, page_img.size)\
            .expand(expand, expand)
        cropped = page_img.crop(image_box.bbox)
        return cropped

    def generate(self, prompt: str, image: PIL.Image.Image, response_schema: content.Schema):
        while True:
            try:
                responses = self.model.generate_content(
                    [prompt, image],
                    stream=False,
                    generation_config={
                        "temperature": 0,
                        "response_schema": response_schema,
                        "response_mime_type": "application/json",
                    }
                )
                output = responses.candidates[0].content.parts[0].text
                return json.loads(output)

            except ResourceExhausted as e:
                print(f"ResourceExhausted: {e}")
                time.sleep(tries * 2)
                tries += 1
            except Exception as e:
                print(e)
                break

        return {}
