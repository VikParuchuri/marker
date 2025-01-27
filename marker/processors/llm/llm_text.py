import json
import textwrap

from marker.processors.llm import BaseLLMProcessor
from bs4 import BeautifulSoup
from google.ai.generativelanguage_v1beta.types import content
from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.registry import get_block_class
from marker.schema.text.span import Span


class LLMTextProcessor(BaseLLMProcessor):
    block_types = (BlockTypes.TextInlineMath,)
    text_math_rewriting_prompt = """You are a text correction expert specializing in accurately reproducing text from images.
You will receive an image of a text block and a set of extracted lines corresponding to the text in the image.
Your task is to correct any errors in the extracted lines, including math, formatting, and other inaccuracies, and output the corrected lines in a JSON format.
The number of output lines MUST match the number of input lines.  Stay as faithful to the original text as possible.

**Instructions:**

1. Carefully examine the provided text block image .
2. Analyze the extracted lines.
3. For each extracted line, compare it to the corresponding line in the image.
4. Correct any errors in the extracted line, including:
    * Inline math: Ensure all mathematical expressions are correctly formatted and rendered.
    * Formatting: Maintain consistent formatting with the text block image, including spacing, indentation, and special characters.
    * Other inaccuracies:  If the image is handwritten then you may correct any spelling errors, or other discrepancies.
5. Do not remove any formatting i.e bold, italics, etc from the extracted lines unless it is necessary to correct the error.
6. Ensure that inline math is properly with inline math tags.
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
  "<math>f(x, w)</math> with parameters <math>w</math>, the optimization objective of\n",
  "AT can be formulated as follows:\n"
 ]
}
```

**Input:**
```json
{extracted_lines}
```
"""

    def process_rewriting(self, document: Document, page: PageGroup, block: Block):
        SpanClass: Span = get_block_class(BlockTypes.Span)

        text_lines = block.contained_blocks(document, (BlockTypes.Line,))
        extracted_lines = [line.formatted_text(document) for line in text_lines]

        prompt = self.text_math_rewriting_prompt.replace("{extracted_lines}", json.dumps({"extracted_lines": extracted_lines}, indent=2))
        image = self.extract_image(document, block)
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

        response = self.model.generate_response(prompt, image, block, response_schema)
        if not response or "corrected_lines" not in response:
            block.update_metadata(llm_error_count=1)
            return

        corrected_lines = response["corrected_lines"]
        if not corrected_lines or len(corrected_lines) != len(extracted_lines):
            block.update_metadata(llm_error_count=1)
            return

        for text_line, corrected_text in zip(text_lines, corrected_lines):
            text_line.structure = []
            corrected_spans = self.text_to_spans(corrected_text)

            for span_idx, span in enumerate(corrected_spans):
                if span_idx == len(corrected_spans) - 1:
                    span['content'] += "\n"

                span_block = page.add_full_block(
                    SpanClass(
                        polygon=text_line.polygon,
                        text=span['content'],
                        font='Unknown',
                        font_weight=0,
                        font_size=0,
                        minimum_position=0,
                        maximum_position=0,
                        formats=[span['type']],
                        page_id=text_line.page_id,
                        text_extraction_method="gemini",
                    )
                )
                text_line.structure.append(span_block.id)

    def text_to_spans(self, text):
        soup = BeautifulSoup(text, 'html.parser')

        tag_types = {
            'b': 'bold',
            'i': 'italic',
            'math': 'math'
        }
        spans = []

        for element in soup.descendants:
            if not len(list(element.parents)) == 1:
                continue
            if element.name in tag_types:
                spans.append({
                    'type': tag_types[element.name],
                    'content': element.get_text()
                })
            elif element.string:
                spans.append({
                    'type': 'plain',
                    'content': element.string
                })

        return spans
