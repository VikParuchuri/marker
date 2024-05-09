from texify.inference import batch_inference

from marker.settings import settings
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"


def get_batch_size():
    if settings.TEXIFY_BATCH_SIZE is not None:
        return settings.TEXIFY_BATCH_SIZE
    elif settings.TORCH_DEVICE_MODEL == "cuda":
        return 6
    elif settings.TORCH_DEVICE_MODEL == "mps":
        return 6
    return 2

def get_latex_batched(images, token_counts, texify_model, batch_multiplier=1):
    if len(images) == 0:
        return []

    predictions = [""] * len(images)
    batch_size = get_batch_size() * batch_multiplier

    for i in range(0, len(images), batch_size):
        # Dynamically set max length to save inference time
        min_idx = i
        max_idx = min(min_idx + batch_size, len(images))
        max_length = max(token_counts[min_idx:max_idx])
        max_length = min(max_length, settings.TEXIFY_MODEL_MAX)
        max_length += settings.TEXIFY_TOKEN_BUFFER

        model_output = batch_inference(images[min_idx:max_idx], texify_model, texify_model.processor, max_tokens=max_length)

        for j, output in enumerate(model_output):
            token_count = get_total_texify_tokens(output, texify_model.processor)
            if token_count >= max_length - 1:
                output = ""

            image_idx = i + j
            predictions[image_idx] = output
    return predictions


def get_total_texify_tokens(text, processor):
    tokenizer = processor.tokenizer
    tokens = tokenizer(text)
    return len(tokens["input_ids"])


