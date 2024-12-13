import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

import google.generativeai as genai
import PIL
from google.ai.generativelanguage_v1beta.types import content
from google.api_core.exceptions import ResourceExhausted
from tqdm import tqdm

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.blocks import Block, BlockId
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.registry import get_block_class
from marker.schema.text.span import Span
from marker.settings import settings

gemini_prompt = """You are a text correction expert specializing in accurately reproducing text from images.
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


class HighQualityTextProcessor(BaseProcessor):
    block_types = (BlockTypes.TextInlineMath, BlockTypes.Handwriting)
    google_api_key: Optional[str] = settings.GOOGLE_API_KEY

    def __init__(self, config):
        super().__init__(config)
        self.model = None

        if self.google_api_key is not None:
            genai.configure(api_key=self.google_api_key)
            self.model = genai.GenerativeModel(
                "gemini-1.5-flash",
                generation_config={
                    "temperature": 0,
                    "response_schema": content.Schema(
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
                    ),
                    "response_mime_type": "application/json",
                }
            )

    def __call__(self, document: Document):
        if self.model is None:
            return

        pbar = tqdm(desc="High quality text processor")
        with ThreadPoolExecutor() as executor:
            future_to_block = {
                executor.submit(self.process_block, document, page, block): block
                for page in document.pages
                for block in page.contained_blocks(document, self.block_types)
            }

            for future in as_completed(future_to_block):
                future.result()  # Raise exceptions if any occurred
                pbar.update(1)

        pbar.close()

    def process_block(self, document: Document, page: PageGroup, block: Block):
        SpanClass: Span = get_block_class(BlockTypes.Span)

        text_lines = block.contained_blocks(document, (BlockTypes.Line,))
        extracted_lines = [line.formatted_text(document) for line in text_lines]
        corrected_lines = self.generate(extracted_lines, self.extract_image(page, block.id))

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
        return block

    def extract_image(self, page: PageGroup, block_id: BlockId, expand: float = 0.01):
        image_block = page.get_block(block_id)
        page_img = page.lowres_image
        image_box = image_block.polygon\
            .rescale(page.polygon.size, page_img.size)\
            .expand(expand, expand)
        cropped = page_img.crop(image_box.bbox)
        return cropped

    def generate(self, extracted_lines: List[str], image: PIL.Image.Image) -> List[str]:
        filled_prompt = gemini_prompt + '```json\n`' + json.dumps({"extracted_lines": extracted_lines}, indent=2) + '`\n```\n'

        while True:
            try:
                responses = self.model.generate_content(
                    [filled_prompt, image],
                    stream=False,
                )
                output = responses.candidates[0].content.parts[0].text
                corrected_lines = json.loads(output)
                return corrected_lines["corrected_lines"]

            except ResourceExhausted as e:
                print(f"ResourceExhausted: {e}")
                time.sleep(tries * 2)
                tries += 1
            except Exception as e:
                print(e)
                break

        return []
