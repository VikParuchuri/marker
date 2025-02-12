import json
from typing import List, Tuple

from pydantic import BaseModel

from marker.processors.llm import BaseLLMSimpleBlockProcessor, PromptData
from bs4 import BeautifulSoup
from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.registry import get_block_class


class LLMTextProcessor(BaseLLMSimpleBlockProcessor):
    block_types = (BlockTypes.Line,)
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
5. Do not remove any formatting i.e bold, italics, math, superscripts, subscripts, etc from the extracted lines unless it is necessary to correct an error.
6. Ensure that inline math is properly with inline math tags.
7. The number of corrected lines in the output MUST equal the number of extracted lines provided in the input. Do not add or remove lines.
8. Output the corrected lines in JSON format with a "lines" field, as shown in the example below.
9. You absolutely cannot remove any <a href='#...'>...</a> tags, those are extremely important for references and are coming directly from the document, you MUST always preserve them.

**Example:**

Input:
```
{
 "extracted_lines": [
  "Adversarial training (AT) <a href='#page-9-1'>[23]</a>, which aims to minimize\n",
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
  "Adversarial training (AT) <a href='#page-9-1'>[23]</a>, which aims to minimize\n",
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

    def get_block_lines(self, block: Block, document: Document) -> Tuple[list, list]:
        text_lines = block.contained_blocks(document, (BlockTypes.Line,))
        extracted_lines = [line.formatted_text(document) for line in text_lines]
        return text_lines, extracted_lines

    def block_prompts(self, document: Document) -> List[PromptData]:
        prompt_data = []
        for block_data in self.inference_blocks(document):
            block = block_data["block"]
            _, extracted_lines = self.get_block_lines(block, document)

            prompt = self.text_math_rewriting_prompt.replace("{extracted_lines}",
                                                             json.dumps({"extracted_lines": extracted_lines}, indent=2))
            image = self.extract_image(document, block)
            prompt_data.append({
                "prompt": prompt,
                "image": image,
                "block": block,
                "schema": LLMTextSchema,
                "page": block_data["page"]
            })
        return prompt_data


    def rewrite_block(self, response: dict, prompt_data: PromptData, document: Document):
        block = prompt_data["block"]
        page = prompt_data["page"]
        SpanClass = get_block_class(BlockTypes.Span)

        text_lines, extracted_lines = self.get_block_lines(block, document)
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
                        url=span.get('url'),
                        page_id=text_line.page_id,
                        text_extraction_method="gemini",
                    )
                )
                text_line.structure.append(span_block.id)

    @staticmethod
    def text_to_spans(text):
        soup = BeautifulSoup(text, 'html.parser')

        tag_types = {
            'b': 'bold',
            'i': 'italic',
            'math': 'math',
        }
        spans = []

        for element in soup.descendants:
            if not len(list(element.parents)) == 1:
                continue

            url = element.attrs.get('href') if hasattr(element, 'attrs') else None

            if element.name in tag_types:
                spans.append({
                    'type': tag_types[element.name],
                    'content': element.get_text(),
                    'url': url
                })
            elif element.string:
                spans.append({
                    'type': 'plain',
                    'content': element.string,
                    'url': url
                })

        return spans

class LLMTextSchema(BaseModel):
    corrected_lines: List[str]