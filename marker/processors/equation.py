from typing import Annotated, List, Optional, Tuple

from texify.inference import batch_inference
from texify.model.model import GenerateVisionEncoderDecoderModel
from tqdm import tqdm

from marker.models import TexifyPredictor
from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.settings import settings


class EquationProcessor(BaseProcessor):
    """
    A processor for recognizing equations in the document.
    """
    block_types: Annotated[
        Tuple[BlockTypes],
        "The block types to process.",
    ] = (BlockTypes.Equation,)
    model_max_length: Annotated[
        int,
        "The maximum number of tokens to allow for the Texify model.",
    ] = 768
    texify_batch_size: Annotated[
        Optional[int],
        "The batch size to use for the Texify model.",
        "Default is None, which will use the default batch size for the model."
    ] = None
    token_buffer: Annotated[
        int,
        "The number of tokens to buffer above max for the Texify model.",
    ] = 256

    def __init__(self, texify_model: TexifyPredictor, config=None):
        super().__init__(config)

        self.texify_model = texify_model

    def __call__(self, document: Document):
        equation_data = []

        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                image = block.get_image(document, highres=False).convert("RGB")
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
            block.html = prediction

    def get_batch_size(self):
        if self.texify_batch_size is not None:
            return self.texify_batch_size
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
            batch_images = [eq["image"] for eq in batch_equations]

            model_output = self.texify_model(
                batch_images
            )

            for j, output in enumerate(model_output):
                token_count = self.get_total_texify_tokens(output.text)
                if token_count >= self.model_max_length - 1:
                    output.text = ""

                image_idx = i + j
                predictions[image_idx] = output.text
        return predictions

    def get_total_texify_tokens(self, text):
        tokenizer = self.texify_model.processor.tokenizer
        tokens = tokenizer(text)
        return len(tokens["input_ids"])