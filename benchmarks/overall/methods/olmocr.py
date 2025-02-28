import base64
import json
import tempfile
import time
from io import BytesIO

import torch
from PIL import Image

from benchmarks.overall.methods import BaseMethod, BenchmarkResult


def convert_single_page(filename: str, model, processor, device):
    from olmocr.data.renderpdf import render_pdf_to_base64png
    from olmocr.prompts import build_finetuning_prompt
    from olmocr.prompts.anchor import get_anchor_text

    image_base64 = render_pdf_to_base64png(filename, 1, target_longest_image_dim=1024)

    # Build the prompt, using document metadata
    anchor_text = get_anchor_text(filename, 1, pdf_engine="pdfreport", target_length=4000)
    prompt = build_finetuning_prompt(anchor_text)

    # Build the full prompt
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
            ],
        }
    ]

    # Apply the chat template and processor
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    main_image = Image.open(BytesIO(base64.b64decode(image_base64)))

    inputs = processor(
        text=[text],
        images=[main_image],
        padding=True,
        return_tensors="pt",
    )
    inputs = {key: value.to(device) for (key, value) in inputs.items()}

    # Generate the output
    output = model.generate(
        **inputs,
        temperature=0.8,
        max_new_tokens=8192,
        num_return_sequences=1,
        do_sample=True,
    )

    # Decode the output
    prompt_length = inputs["input_ids"].shape[1]
    new_tokens = output[:, prompt_length:]
    text_output = processor.tokenizer.batch_decode(
        new_tokens, skip_special_tokens=True
    )[0]

    try:
        text_output = json.loads(text_output)
        text = text_output["natural_text"]
    except Exception:
        try:
            text = text_output.split("natural_text")[1].strip()
        except Exception:
            text = ""

    return text


class OlmOCRMethod(BaseMethod):
    olmocr_model: dict = None
    use_llm: bool = False

    def __call__(self, sample) -> BenchmarkResult:
        pdf_bytes = sample["pdf"]  # This is a single page PDF

        with tempfile.NamedTemporaryFile(suffix=".pdf", mode="wb") as f:
            f.write(pdf_bytes)
            start = time.time()
            result = convert_single_page(f.name, self.olmocr_model["model"], self.olmocr_model["processor"], self.olmocr_model["model"].device)
            total = time.time() - start

        return {
            "markdown": result,
            "time": total
        }
