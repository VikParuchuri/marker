import base64
import json
import time
from io import BytesIO
from typing import List, Annotated, Union, T

import PIL
from PIL import Image
import anthropic
from anthropic import APIError, APIConnectionError, APITimeoutError, RateLimitError
from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.services import BaseService

class ClaudeService(BaseService):
    claude_model_name: Annotated[
        str,
        "The name of the Google model to use for the service."
    ] = "claude-3-5-sonnet-20241022"
    claude_api_key: Annotated[
        str,
        "The Claude API key to use for the service."
    ] = None
    max_claude_tokens: Annotated[
        int,
        "The maximum number of tokens to use for a single Claude request."
    ] = 4096


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
        try:
            # Try to parse as JSON first
            data = json.loads(response_text)
            return schema.parse_obj(data)
        except json.JSONDecodeError:
            # If not JSON, try to parse the raw text into the schema
            return schema.parse_raw(response_text)

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
""".strip()

        client = self.get_client()
        image_data = self.prepare_images(image)

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    *image_data
                ]
            }
        ]

        tries = 0
        while tries < max_retries:
            try:
                response = client.messages.create(
                    model=self.claude_model_name,
                    max_tokens=self.max_claude_tokens,
                    messages=messages,
                    timeout=timeout
                )
                # Extract and validate response
                response_text = response.content[0].text
                return self.validate_response(response_text, response_schema)
            except RateLimitError as e:
                # Rate limit exceeded
                tries += 1
                wait_time = tries * 3
                print(f"Rate limit error: {e}. Retrying in {wait_time} seconds... (Attempt {tries}/{max_retries})")
                time.sleep(wait_time)
            except Exception as e:
                print(e)
                break

        return {}