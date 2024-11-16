from typing import List, Optional

from pydantic import BaseModel
from texify.inference import batch_inference
from tqdm import tqdm

from marker.settings import settings
from marker.v2.processors import BaseProcessor
from marker.v2.schema import BlockTypes
from marker.v2.schema.document import Document


class EquationProcessor(BaseProcessor):
    block_type = BlockTypes.Equation
    model_max_length = 384
    batch_size = None
    token_buffer = 256

    def __init__(self, texify_model, config: Optional[BaseModel] = None):
        super().__init__(config)

        self.texify_model = texify_model

    def __call__(self, document: Document):
        equation_data = []

        for page in document.pages:
            for block in page.children:
                if block.block_type != self.block_type:
                    continue
                image_poly = block.polygon.rescale((page.polygon.width, page.polygon.height), page.lowres_image.size)
                image = page.lowres_image.crop(image_poly.bbox).convert("RGB")
                raw_text = block.raw_text(document)
                token_count = self.get_total_texify_tokens(raw_text)

                equation_data.append({
                    "image": image,
                    "block_id": block.id,
                    "token_count": token_count
                })

        predictions = self.get_latex_batched(equation_data)
        for prediction, equation_d in zip(predictions, equation_data):
            conditions = [
                self.get_total_texify_tokens(prediction) < self.model_max_length,
                # Make sure we didn't get to the overall token max, indicates run-on
                len(prediction) > equation_d["token_count"] * .4,
                len(prediction.strip()) > 0
            ]
            if not all(conditions):
                continue

            block = document.get_block(equation_d["block_id"])
            block.latex = prediction

    def get_batch_size(self):
        if self.batch_size is not None:
            return self.batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 6
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 6
        return 2

    def get_latex_batched(self, equation_data: List[dict]):
        predictions = [""] * len(equation_data)
        batch_size = self.get_batch_size()

        for i in tqdm(range(0, len(equation_data), batch_size), desc="Recognizing equations"):
            # Dynamically set max length to save inference time
            min_idx = i
            max_idx = min(min_idx + batch_size, len(equation_data))

            batch_equations = equation_data[min_idx:max_idx]
            max_length = max([eq["token_count"] for eq in batch_equations])
            max_length = min(max_length, self.model_max_length)
            max_length += self.token_buffer

            batch_images = [eq["image"] for eq in batch_equations]

            model_output = batch_inference(
                batch_images,
                self.texify_model,
                self.texify_model.processor,
                max_tokens=max_length
            )

            for j, output in enumerate(model_output):
                token_count = self.get_total_texify_tokens(output)
                if token_count >= max_length - 1:
                    output = ""

                image_idx = i + j
                predictions[image_idx] = output
        return predictions

    def get_total_texify_tokens(self, text):
        tokenizer = self.texify_model.processor.tokenizer
        tokens = tokenizer(text)
        return len(tokens["input_ids"])
