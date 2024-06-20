from collections import defaultdict
from itertools import chain
from typing import Optional

from marker.settings import settings
import torch
import torch.nn.functional as F
from marker.postprocessors.t5 import T5ForTokenClassification, byt5_tokenize


def get_batch_size():
    if settings.EDITOR_BATCH_SIZE is not None:
        return settings.EDITOR_BATCH_SIZE
    elif settings.TORCH_DEVICE_MODEL == "cuda":
        return 12
    return 6


def load_editing_model(device=None, dtype=None):
    if not settings.ENABLE_EDITOR_MODEL:
        return None

    if device:
        model = T5ForTokenClassification.from_pretrained(
            settings.EDITOR_MODEL_NAME,
            torch_dtype=dtype,
            device=device,
        )
    else:
        model = T5ForTokenClassification.from_pretrained(
                settings.EDITOR_MODEL_NAME,
                torch_dtype=settings.MODEL_DTYPE,
            ).to(settings.TORCH_DEVICE_MODEL)
    model.eval()

    model.config.label2id = {
        "equal": 0,
        "delete": 1,
        "newline-1": 2,
        "space-1": 3,
    }
    model.config.id2label = {v: k for k, v in model.config.label2id.items()}
    return model


def edit_full_text(text: str, model: Optional[T5ForTokenClassification], batch_multiplier=1) -> (str, dict):
    if not model:
        return text, {}

    batch_size = get_batch_size() * batch_multiplier
    tokenized = byt5_tokenize(text, settings.EDITOR_MAX_LENGTH)
    input_ids = tokenized["input_ids"]
    char_token_lengths = tokenized["char_token_lengths"]

    # Run model
    token_masks = []
    for i in range(0, len(input_ids), batch_size):
        batch_input_ids = tokenized["input_ids"][i: i + batch_size]
        batch_input_ids = torch.tensor(batch_input_ids, device=model.device)
        batch_attention_mask = tokenized["attention_mask"][i: i + batch_size]
        batch_attention_mask = torch.tensor(batch_attention_mask, device=model.device)
        with torch.inference_mode():
            predictions = model(batch_input_ids, attention_mask=batch_attention_mask)

        logits = predictions.logits.cpu()

        # If the max probability is less than a threshold, we assume it's a bad prediction
        # We want to be conservative to not edit the text too much
        probs = F.softmax(logits, dim=-1)
        max_prob = torch.max(probs, dim=-1)
        cutoff_prob = max_prob.values < settings.EDITOR_CUTOFF_THRESH
        labels = logits.argmax(-1)
        labels[cutoff_prob] = model.config.label2id["equal"]
        labels = labels.squeeze().tolist()
        if len(labels) == settings.EDITOR_MAX_LENGTH:
            labels = [labels]
        labels = list(chain.from_iterable(labels))
        token_masks.extend(labels)

    # List of characters in the text
    flat_input_ids = list(chain.from_iterable(input_ids))

    # Strip special tokens 0,1.  Keep unknown token, although it should never be used
    assert len(token_masks) == len(flat_input_ids)
    token_masks = [mask for mask, token in zip(token_masks, flat_input_ids) if token >= 2]

    assert len(token_masks) == len(list(text.encode("utf-8")))

    edit_stats = defaultdict(int)
    out_text = []
    start = 0
    for i, char in enumerate(text):
        char_token_length = char_token_lengths[i]
        masks = token_masks[start: start + char_token_length]
        labels = [model.config.id2label[mask] for mask in masks]
        if all(l == "delete" for l in labels):
            # If we delete whitespace, roll with it, otherwise ignore
            if char.strip():
                out_text.append(char)
            else:
                edit_stats["delete"] += 1
        elif labels[0] == "newline-1":
            out_text.append("\n")
            out_text.append(char)
            edit_stats["newline-1"] += 1
        elif labels[0] == "space-1":
            out_text.append(" ")
            out_text.append(char)
            edit_stats["space-1"] += 1
        else:
            out_text.append(char)
            edit_stats["equal"] += 1

        start += char_token_length

    out_text = "".join(out_text)
    return out_text, edit_stats






