from collections import defaultdict, Counter
from itertools import chain
from typing import Optional
import re

from transformers import BloomForTokenClassification, AutoTokenizer
from marker.settings import settings
import torch
import torch.nn.functional as F
from marker.postprocessors.t5 import T5ForTokenClassification

tokenizer = AutoTokenizer.from_pretrained(settings.EDITOR_MODEL_NAME)


def load_editing_model():
    if not settings.ENABLE_EDITOR_MODEL:
        return None

    model = T5ForTokenClassification.from_pretrained(
            settings.EDITOR_MODEL_NAME
        ).to(settings.TORCH_DEVICE)

    if settings.CUDA:
        model = model.to(torch.bfloat16)

    model.config.label2id = {
        "equal": 0,
        "delete": 1,
        "newline-1": 2,
        "space-1": 3,
    }
    model.config.id2label = {v: k for k, v in model.config.label2id.items()}
    return model


def edit_full_text(text: str, model: Optional[T5ForTokenClassification], batch_size: int = settings.EDITOR_BATCH_SIZE):
    if not model:
        return text, {}

    tokenized = tokenizer(
        text,
        truncation=True,
        max_length=settings.EDITOR_MAX_LENGTH,
        return_overflowing_tokens=True,
        padding="max_length",
    )
    input_ids = tokenized["input_ids"]

    # Tokenize, and make sure reverse tokenization works
    model_tokens = [tokenizer.convert_ids_to_tokens(t, skip_special_tokens=True) for t in input_ids]
    full_text = "".join(model_tokens)
    assert full_text == text

    # List of characters in the text
    model_tokens = [tokenizer.convert_ids_to_tokens(t) for t in input_ids]
    flat_model_tokens = list(chain.from_iterable(model_tokens))
    flat_str_tokens = list(text)

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
        cutoff_prob = max_prob.values < 0.9
        labels = logits.argmax(-1).squeeze()
        labels[cutoff_prob] = model.config.label2id["equal"]

        labels = labels.tolist()
        if len(labels) == settings.EDITOR_MAX_LENGTH:
            labels = [labels]
        labels = list(chain.from_iterable(labels))
        token_masks.extend(labels)

    # Strip special tokens
    assert len(token_masks) == len(flat_model_tokens)
    token_masks = [mask for mask, token in zip(token_masks, flat_model_tokens) if token not in ["<pad>", "<s>", "</s>"]]

    assert len(token_masks) == len(flat_str_tokens)

    edit_stats = defaultdict(int)
    out_tokens = []
    for i, (str_token, mask) in enumerate(zip(flat_str_tokens, token_masks)):
        label = model.config.id2label[mask]

        match label:
            case "equal":
                out_tokens.append(str_token)
                edit_stats[label] += 1
            case "delete":
                # If we delete whitespace, roll with it, otherwise ignore
                if str_token.strip():
                    out_tokens.append(str_token)
                else:
                    edit_stats[label] += 1
            case "newline-1":
                out_tokens.append("\n")
                out_tokens.append(str_token)
                edit_stats[label] += 1
            case "space-1":
                out_tokens.append(" ")
                out_tokens.append(str_token)
                edit_stats[label] += 1

    return "".join(out_tokens), edit_stats






