from pydantic import BaseModel

from marker.processors.llm import BaseLLMSimpleBlockProcessor, PromptData, BlockData
from marker.schema import BlockTypes
from marker.schema.document import Document

from typing import Annotated, List


class LLMEquationProcessor(BaseLLMSimpleBlockProcessor):
    block_types = (BlockTypes.Equation,)
    min_equation_height: Annotated[
        float,
        "The minimum ratio between equation height and page height to consider for processing.",
     ] = 0.06
    image_expansion_ratio: Annotated[
        float,
        "The ratio to expand the image by when cropping.",
    ] = 0.05 # Equations sometimes get bboxes that are too tight
    redo_inline_math: Annotated[
        bool,
        "Whether to redo inline math blocks.",
    ] = False
    equation_latex_prompt: Annotated[
        str,
        "The prompt to use for generating LaTeX from equations.",
        "Default is a string containing the Gemini prompt."
    ] = r"""You're an expert mathematician who is good at writing LaTeX code and html for equations.
You'll receive an image of a math block that may contain one or more equations. Your job is to write html that represents the content of the image, with the equations in LaTeX format, and fenced by delimiters.

Some guidelines:
- Output valid html, where all the equations can render properly.
- Use <math display="block"> as a block equation delimiter and <math> for inline equations.  Do not use $ or $$ as delimiters.
- Keep the LaTeX code inside the math tags simple, concise, and KaTeX compatible.
- Enclose all equations in the correct math tags. Use multiple math tags inside the html to represent multiple equations.
- Only use the html tags math, i, b, p, and br.
- Make sure to include all the equations in the image in the html output.

**Instructions:**
1. Carefully examine the provided image.
2. Analyze the existing html, which may include LaTeX code.
3. If the html and LaTeX are correct, write "No corrections needed."
4. If the html and LaTeX are incorrect, generate the corrected html.
5. Output only the corrected html or "No corrections needed."
**Example:**
Input:
```html
Equation 1: 
<math display="block">x2 + y2 = z2</math>
Equation 2:
<math display="block">\frac{ab \cdot x^5 + x^2 + 2 \cdot x + 123}{t}</math>
```
Output:
```html
<p>Equation 1:</p> 
<math display="block">x^{2} + y^{2} = z^{2}</math>
<p>Equation 2:</p>
<math display="block">\frac{ab \cdot x^{5} + x^{2} + 2 \cdot x + 123}{t}</math>
```
**Input:**
```html
{equation}
```
"""

    def inference_blocks(self, document: Document) -> List[BlockData]:
        blocks = super().inference_blocks(document)
        out_blocks = []
        for block_data in blocks:
            block = block_data["block"]
            page = block_data["page"]
            # If we redo inline math, we redo all equations
            if block.polygon.height / page.polygon.height < self.min_equation_height and not self.redo_inline_math:
                continue
            out_blocks.append(block_data)
        return out_blocks

    def block_prompts(self, document: Document) -> List[PromptData]:
        prompt_data = []
        for block_data in self.inference_blocks(document):
            block = block_data["block"]
            text = block.html if block.html else block.raw_text(document)
            prompt = self.equation_latex_prompt.replace("{equation}", text)
            image = self.extract_image(document, block)

            prompt_data.append({
                "prompt": prompt,
                "image": image,
                "block": block,
                "schema": EquationSchema,
                "page": block_data["page"]
            })

        return prompt_data


    def rewrite_block(self, response: dict, prompt_data: PromptData, document: Document):
        block = prompt_data["block"]
        text = block.html if block.html else block.raw_text(document)

        if not response or "html_equation" not in response:
            block.update_metadata(llm_error_count=1)
            return

        html_equation = response["html_equation"]
        balanced_tags = html_equation.count("<math") == html_equation.count("</math>")
        if not all([
            html_equation,
            balanced_tags,
            len(html_equation) > len(text) * .3,
        ]):
            block.update_metadata(llm_error_count=1)
            return

        block.html = html_equation

class EquationSchema(BaseModel):
    html_equation: str
