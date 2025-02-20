import base64
import json
from io import BytesIO
from typing import Annotated, List

import PIL
import requests
from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.services import BaseService


class OllamaService(BaseService):
    ollama_base_url: Annotated[
        str,
        "The base url to use for ollama.  No trailing slash."
    ] = "http://localhost:11434"
    ollama_model: Annotated[
        str,
        "The model name to use for ollama."
    ] = "llama3.2-vision"

    def image_to_base64(self, image: PIL.Image.Image):
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        return base64.b64encode(image_bytes.getvalue()).decode("utf-8")

    def __call__(
        self,
        prompt: str,
        image: PIL.Image.Image | List[PIL.Image.Image],
        block: Block,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None
    ):
        url = f"{self.ollama_base_url}/api/generate"
        headers = {"Content-Type": "application/json"}

        schema = response_schema.model_json_schema()
        format_schema = {
            "type": "object",
            "properties": schema["properties"],
            "required": schema["required"]
        }

        if not isinstance(image, list):
            image = [image]

        image_bytes = [self.image_to_base64(img) for img in image]

        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": format_schema,
            "images": image_bytes
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            response_data = response.json()

            total_tokens = response_data["prompt_eval_count"] + response_data["eval_count"]
            block.update_metadata(llm_request_count=1, llm_tokens_used=total_tokens)

            data = response_data["response"]
            return json.loads(data)
        except Exception as e:
            print(f"Ollama inference failed: {e}")

        return {}