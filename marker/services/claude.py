import base64
import json
import time
from io import BytesIO
from typing import List, Annotated, Union, T

import PIL
from PIL import Image
import anthropic
from anthropic import RateLimitError, APITimeoutError
from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.services import BaseService

class ClaudeService(BaseService):
    claude_model_name: Annotated[
        str,
        "The name of the Google model to use for the service."
    ] = "claude-3-7-sonnet-20250219"
    claude_api_key: Annotated[
        str,
        "The Claude API key to use for the service."
    ] = None
    max_claude_tokens: Annotated[
        int,
        "The maximum number of tokens to use for a single Claude request."
    ] = 8192


    def img_to_base64(self, img: PIL.Image.Image):
        image_bytes = BytesIO()
        img.save(image_bytes, format="WEBP")
        return base64.b64encode(image_bytes.getvalue()).decode('utf-8')

    def prepare_images(self, images: Union[Image.Image, List[Image.Image]]) -> List[dict]:
        if isinstance(images, Image.Image):
            images = [images]

        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/webp",
                    "data": self.img_to_base64(img)
                }
            }
            for img in images
        ]

    def validate_response(self, response_text: str, schema: type[T]) -> T:
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        try:
            # Try to parse as JSON first
            out_schema = schema.model_validate_json(response_text)
            out_json = out_schema.model_dump()
            return out_json
        except Exception as e:
            try:
                # Re-parse with fixed escapes
                escaped_str = response_text.replace('\\', '\\\\')
                out_schema = schema.model_validate_json(escaped_str)
                return out_schema.model_dump()
            except Exception as e:
                return

    def get_client(self):
        return anthropic.Anthropic(
            api_key=self.claude_api_key,
        )

    def __call__(
            self,
            prompt: str,
            image: PIL.Image.Image | List[PIL.Image.Image],
            block: Block,
            response_schema: type[BaseModel],
            max_retries: int | None = None,
            timeout: int | None = None
    ):
        if max_retries is None:
            max_retries = self.max_retries

        if timeout is None:
            timeout = self.timeout

        if not isinstance(image, list):
            image = [image]

        schema_example = response_schema.model_json_schema()
        system_prompt = f"""
Follow the instructions given by the user prompt.  You must provide your response in JSON format matching this schema:

{json.dumps(schema_example, indent=2)}

Respond only with the JSON schema, nothing else.  Do not include ```json, ```,  or any other formatting.
""".strip()

        client = self.get_client()
        image_data = self.prepare_images(image)

        messages = [
            {
                "role": "user",
                "content": [
                    *image_data,
                    {
                        "type": "text",
                        "text": prompt
                    },
                ]
            }
        ]

        tries = 0
        while tries < max_retries:
            try:
                response = client.messages.create(
                    system=system_prompt,
                    model=self.claude_model_name,
                    max_tokens=self.max_claude_tokens,
                    messages=messages,
                    timeout=timeout
                )
                # Extract and validate response
                response_text = response.content[0].text
                return self.validate_response(response_text, response_schema)
            except (RateLimitError, APITimeoutError) as e:
                # Rate limit exceeded
                tries += 1
                wait_time = tries * 3
                print(f"Rate limit error: {e}. Retrying in {wait_time} seconds... (Attempt {tries}/{max_retries})")
                time.sleep(wait_time)
            except Exception as e:
                print(e)
                break

        return {}