from typing import Annotated, List, Optional, Tuple

from surya.texify import TexifyPredictor
from marker.processors import BaseProcessor
from marker.processors.util import add_math_spans_to_line
from marker.schema import BlockTypes
from marker.schema.blocks import Equation
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
    disable_tqdm: Annotated[
        bool,
        "Whether to disable the tqdm progress bar.",
    ] = False
    texify_inline_spans: Annotated[
        bool,
        "Whether to run texify on inline math spans."
    ] = False

    def __init__(self, texify_model: TexifyPredictor, config=None):
        super().__init__(config)

        self.texify_model = texify_model

    def __call__(self, document: Document):
        equation_data = []

        for page in document.pages:
            equation_blocks = page.contained_blocks(document, self.block_types)
            math_blocks = []
            if self.texify_inline_spans:
                math_blocks = page.contained_blocks(document, (BlockTypes.Line,))
                math_blocks = [m for m in math_blocks if m.formats and "math" in m.formats]

            for block in equation_blocks + math_blocks:
                image = block.get_image(document, highres=False).convert("RGB")
                raw_text = block.raw_text(document)
                token_count = self.get_total_texify_tokens(raw_text)

                equation_data.append({
                    "image": image,
                    "block_id": block.id,
                    "token_count": token_count,
                    "page": page
                })

        if len(equation_data) == 0:
            return

        predictions = self.get_latex_batched(equation_data)
        for prediction, equation_d in zip(predictions, equation_data):
            conditions = [
                len(prediction) > equation_d["token_count"] * .4,
                len(prediction.strip()) > 0
            ]
            if not all(conditions):
                continue

            block = document.get_block(equation_d["block_id"])
            if isinstance(block, Equation):
                prediction = self.inline_to_block(prediction)
                block.html = prediction
            else:
                block.structure = []
                add_math_spans_to_line(prediction, block, equation_d["page"])

    def inline_to_block(self, latex: str):
        latex = latex.strip()
        math_count = latex.count("<math")
        math_start = latex.startswith("<math>")
        math_end = latex.endswith("</math>")
        if any([
            math_count != 1,
            not math_start,
            not math_end
        ]):
            return latex

        latex = latex.replace("<math>", '<math display="block">')
        return latex


    def get_batch_size(self):
        if self.texify_batch_size is not None:
            return self.texify_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 6
        elif settings.TORCH_DEVICE_MODEL == "mps":
            return 6
        return 2

    def get_latex_batched(self, equation_data: List[dict]):
        inference_images = [eq["image"] for eq in equation_data]
        self.texify_model.disable_tqdm = self.disable_tqdm
        model_output = self.texify_model(inference_images, batch_size=self.get_batch_size())
        predictions = [output.text for output in model_output]

        for i, pred in enumerate(predictions):
            token_count = self.get_total_texify_tokens(pred)
            # If we're at the max token length, the prediction may be repetitive or invalid
            if token_count >= self.model_max_length - 1:
                predictions[i] = ""
        return predictions

    def get_total_texify_tokens(self, text):
        tokenizer = self.texify_model.processor.tokenizer
        tokens = tokenizer(text)
        return len(tokens["input_ids"])