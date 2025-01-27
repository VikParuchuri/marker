from marker.processors.llm import BaseLLMProcessor

from google.ai.generativelanguage_v1beta.types import content

from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup

from typing import Annotated


class LLMImageDescriptionProcessor(BaseLLMProcessor):
    block_types = (BlockTypes.Picture, BlockTypes.Figure,)
    extract_images: Annotated[
        bool,
        "Extract images from the document."
    ] = True
    image_description_prompt: Annotated[
        str,
        "The prompt to use for generating image descriptions.",
        "Default is a string containing the Gemini prompt."
    ] = """You are a document analysis expert who specializes in creating text descriptions for images.
You will receive an image of a picture or figure.  Your job will be to create a short description of the image.
**Instructions:**
1. Carefully examine the provided image.
2. Analyze any text that was extracted from within the image.
3. Output a 3-4 sentence description of the image.  Make sure there is enough specific detail to accurately describe the image.  If there are numbers included, try to be specific.
**Example:**
Input:
```text
"Fruit Preference Survey"
20, 15, 10
Apples, Bananas, Oranges
```
Output:
In this figure, a bar chart titled "Fruit Preference Survey" is showing the number of people who prefer different types of fruits.  The x-axis shows the types of fruits, and the y-axis shows the number of people.  The bar chart shows that most people prefer apples, followed by bananas and oranges.  20 people prefer apples, 15 people prefer bananas, and 10 people prefer oranges.
**Input:**
```text
{raw_text}
```
"""

    def process_rewriting(self, document: Document, page: PageGroup, block: Block):
        if self.extract_images:
            # We will only run this processor if we're not extracting images
            # Since this processor replaces images with descriptions
            return

        prompt = self.image_description_prompt.replace("{raw_text}", block.raw_text(document))
        image = self.extract_image(document, block)
        response_schema = content.Schema(
            type=content.Type.OBJECT,
            enum=[],
            required=["image_description"],
            properties={
                "image_description": content.Schema(
                    type=content.Type.STRING
                )
            },
        )

        response = self.model.generate_response(prompt, image, block, response_schema)

        if not response or "image_description" not in response:
            block.update_metadata(llm_error_count=1)
            return

        image_description = response["image_description"]
        if len(image_description) < 10:
            block.update_metadata(llm_error_count=1)
            return

        block.description = image_description
