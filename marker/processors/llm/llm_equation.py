from marker.processors.llm import BaseLLMProcessor

from google.ai.generativelanguage_v1beta.types import content

from marker.schema import BlockTypes
from marker.schema.blocks import Equation
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup

from typing import Annotated


class LLMEquationProcessor(BaseLLMProcessor):
    block_types = (BlockTypes.Equation,)
    min_equation_height: Annotated[
        float,
        "The minimum ratio between equation height and page height to consider for processing.",
     ] = 0.08
    equation_image_expansion_ratio: Annotated[
        float,
        "The ratio to expand the image by when cropping.",
    ] = 0.05 # Equations sometimes get bboxes that are too tight
    equation_latex_prompt: Annotated[
        str,
        "The prompt to use for generating LaTeX from equations.",
        "Default is a string containing the Gemini prompt."
    ] = """You're an expert mathematician who is good at writing LaTeX code and html for equations.
You'll receive an image of a math block that may contain one or more equations. Your job is to write html that represents the content of the image, with the equations in LaTeX format, and fenced by delimiters.

Some guidelines:
- Output valid html, where all the equations can render properly.
- Use <math display="block"> as a block equation delimiter and <math> for inline equations.
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

    def process_rewriting(self, document: Document, page: PageGroup, block: Equation):
        text = block.html if block.html else block.raw_text(document)
        prompt = self.equation_latex_prompt.replace("{equation}", text)

        image = self.extract_image(document, block)
        response_schema = content.Schema(
            type=content.Type.OBJECT,
            enum=[],
            required=["html_equation"],
            properties={
                "html_equation": content.Schema(
                    type=content.Type.STRING
                )
            },
        )

        response = self.model.generate_response(prompt, image, block, response_schema)

        if not response or "html_equation" not in response:
            block.update_metadata(llm_error_count=1)
            return

        html_equation = response["html_equation"]
        if len(html_equation) < len(text) * .5:
            block.update_metadata(llm_error_count=1)
            return
        block.html = html_equation
