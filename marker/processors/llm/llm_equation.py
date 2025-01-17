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
     ] = 0.1
    equation_latex_prompt: Annotated[
        str,
        "The prompt to use for generating LaTeX from equations.",
        "Default is a string containing the Gemini prompt."
    ] = """You're an expert mathematician who is good at writing LaTeX code for equations'.
You will receive an image of a math block that may contain one or more equations. Your job is to write the LaTeX code for the equation, along with markdown for any other text.

Some guidelines:
- Keep the LaTeX code simple and concise.
- Make it KaTeX compatible.
- Use $$ as a block equation delimiter and $ for inline equations.  Block equations should also be on their own line.  Do not use any other delimiters.
- You can include text in between equation blocks as needed.  Try to put long text segments into plain text and not inside the equations.

**Instructions:**
1. Carefully examine the provided image.
2. Analyze the existing markdown, which may include LaTeX code.
3. If the markdown and LaTeX are correct, write "No corrections needed."
4. If the markdown and LaTeX are incorrect, generate the corrected markdown and LaTeX.
5. Output only the corrected text or "No corrections needed."
**Example:**
Input:
```markdown
Equation 1: 
$$x^2 + y^2 = z2$$
```
Output:
```markdown
Equation 1: 
$$x^2 + y^2 = z^2$$
```
**Input:**
```markdown
{equation}
```
"""

    def process_rewriting(self, document: Document, page: PageGroup, block: Equation):
        text = block.latex if block.latex else block.raw_text(document)
        prompt = self.equation_latex_prompt.replace("{equation}", text)

        image = self.extract_image(document, block)
        response_schema = content.Schema(
            type=content.Type.OBJECT,
            enum=[],
            required=["markdown_equation"],
            properties={
                "markdown_equation": content.Schema(
                    type=content.Type.STRING
                )
            },
        )

        response = self.model.generate_response(prompt, image, block, response_schema)

        if not response or "markdown_equation" not in response:
            block.update_metadata(llm_error_count=1)
            return

        markdown_equation = response["markdown_equation"]
        if len(markdown_equation) < len(text) * .5:
            block.update_metadata(llm_error_count=1)
            return

        block.latex = markdown_equation
