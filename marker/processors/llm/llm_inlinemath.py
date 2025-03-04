import json
from typing import List, Tuple, Annotated

from pydantic import BaseModel
from PIL import Image

from marker.processors.llm import BaseLLMSimpleBlockProcessor, PromptData, BlockData

from marker.processors.util import add_math_spans_to_line
from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.text import Line


class LLMInlineMathLinesProcessor(BaseLLMSimpleBlockProcessor):
    math_line_batch_size: Annotated[
        int,
        "The number of math lines to batch together.",
    ] = 10

    block_types = (BlockTypes.Line,)
    image_remove_blocks = (BlockTypes.Equation,)
    text_math_rewriting_prompt = r"""You are a text correction expert specializing in accurately reproducing text from images.
You will receive an image of a text block and a set of extracted lines corresponding to the text in the image.
Your task is to correct any errors in the extracted lines, including math, formatting, and other inaccuracies, and output the corrected lines in a JSON format.

The number of output lines MUST match the number of input lines.  Stay as faithful to the original text as possible.

**Instructions:**

1. Carefully examine the provided text block image .
2. Analyze the extracted lines.
3. Write a short analysis comparing the extracted lines to the image.
4. For each extracted line, compare it to the corresponding line in the image.
5. Correct any errors in the extracted line, including:
    * Inline math: Ensure all mathematical expressions are correctly formatted and rendered.  Use the `<math>` and `</math>` tags to surround inline math properly.  Make sure the opening and closing tags appear in pairs, on the same line.  The math should be written in simple, concise, KaTeX-compatible LaTeX.  Do not use $ or $$ as delimiters.
    * Formatting: Maintain consistent formatting with the text block image, including spacing, indentation, subscripts/superscripts, and special characters.  Use the `<i>`, `<b>`, `<sup>`, `<sub>`, and `<span>` tags to format the text as needed.
    * Other inaccuracies:  If the image is handwritten then you may correct any spelling errors, or other discrepancies.
6. Do not remove any formatting i.e bold, italics, math, superscripts, subscripts, etc from the extracted lines unless it is necessary to correct an error.  The formatting 
7. The number of corrected lines in the output MUST equal the number of extracted lines provided in the input. Do not add or remove lines.  There are exactly {line_count} input lines.
8. Output the corrected lines in JSON format, as shown in the example below.  Each line should be in HTML format. Only use the math, br, a, i, b, sup, sub, and span tags.
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
analysis: The inline math in the lines is not in LaTeX format and is not surrounded by <math>...</math> tags.
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

    def inference_blocks(self, document: Document) -> List[List[BlockData]]:
        blocks = []
        for page in document.pages:
            page_children = [p for p in page.children if p.structure]
            for block in page.contained_blocks(document, self.block_types):
                # Ensure the line isn't an orphan, and that the parent hasn't already been inferenced (assigned html)
                has_parent = any([
                    (
                        block.id in parent.structure
                        and not getattr(parent, "html", None)
                    )
                    for parent in page_children
                ])

                if block.formats and "math" in block.formats and has_parent:
                    blocks.append({
                        "page": page,
                        "block": block
                    })


        out_blocks = []
        for i in range(0, len(blocks), self.math_line_batch_size):
            batch = blocks[i:i + self.math_line_batch_size]
            out_blocks.append(batch)
        return out_blocks

    def get_block_lines(self, block: Block, document: Document) -> Tuple[list, list]:
        text_lines = block.contained_blocks(document, (BlockTypes.Line,))
        extracted_lines = [line.formatted_text(document) for line in text_lines]
        return text_lines, extracted_lines

    def combine_images(self, images: List[Image.Image]):
        widths, heights = zip(*(i.size for i in images))
        total_width = max(widths)
        total_height = sum(heights) + 5 * len(images)

        new_im = Image.new('RGB', (total_width, total_height), (255, 255, 255))

        y_offset = 0
        for im in images:
            new_im.paste(im, (0, y_offset))
            y_offset += im.size[1] + 5

        return new_im

    def block_prompts(self, document: Document) -> List[PromptData]:
        prompt_data = []
        for block_data in self.inference_blocks(document):
            blocks: List[Line] = [b["block"] for b in block_data]
            pages = [b["page"] for b in block_data]
            block_lines = [block.formatted_text(document) for block in blocks]

            prompt = (
                self.text_math_rewriting_prompt
                  .replace("{extracted_lines}",json.dumps({"extracted_lines": block_lines}, indent=2))
                  .replace("{line_count}", str(len(block_lines)))
            )
            images = [self.extract_image(document, block, remove_blocks=self.image_remove_blocks) for block in blocks]
            image = self.combine_images(images)

            prompt_data.append({
                "prompt": prompt,
                "image": image,
                "block": blocks[0],
                "schema": LLMTextSchema,
                "page": pages[0],
                "additional_data": {"blocks": blocks, "pages": pages}
            })
        return prompt_data


    def rewrite_block(self, response: dict, prompt_data: PromptData, document: Document):
        blocks = prompt_data["additional_data"]["blocks"]
        pages = prompt_data["additional_data"]["pages"]

        if not response or "corrected_lines" not in response:
            blocks[0].update_metadata(llm_error_count=1)
            return

        corrected_lines = response["corrected_lines"]
        balanced_math = all([line.count("<math") == line.count("</math>") for line in corrected_lines])
        if any([
            not corrected_lines,
            len(corrected_lines) != len(blocks),
            not balanced_math
        ]):
            blocks[0].update_metadata(llm_error_count=1)
            return

        for text_line, page, corrected_text in zip(blocks, pages, corrected_lines):
            text_line.structure = []
            add_math_spans_to_line(corrected_text, text_line, page)

class LLMTextSchema(BaseModel):
    analysis: str
    corrected_lines: List[str]