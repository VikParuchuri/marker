from collections import defaultdict, Counter
from itertools import chain
from typing import Optional
import re

from transformers import BloomForTokenClassification, AutoTokenizer, DataCollatorForTokenClassification
from marker.settings import settings
import torch

tokenizer = AutoTokenizer.from_pretrained(settings.EDITOR_MODEL_NAME)


def load_editing_model(disable_editor=False):
    if disable_editor:
        return None

    if not settings.CUDA:
        # Don't postprocess on CPU to save time
        return None

    model = BloomForTokenClassification.from_pretrained(
        settings.EDITOR_MODEL_NAME,
        load_in_4bit=True,
        torch_dtype=torch.bfloat16,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_type="nf4",
        device_map="sequential"
    )

    model.config.label2id = {
        "equal": 0,
        "delete": 1,
        "delete_trailing_newline": 2,
        "delete_leading_space": 3,
        "leading_space_to_newline": 4,
        "newline-1": 5,
        "space-1": 6,
    }
    model.config.id2label = {v: k for k, v in model.config.label2id.items()}
    return model


def edit_full_text(text: str, model: Optional[BloomForTokenClassification]):
    if not model:
        return text

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
    model_str_tokens = [tokenizer.convert_tokens_to_string(t) for t in model_tokens]
    full_text = "".join(model_str_tokens)
    assert full_text == text

    # Long list of all tokens
    model_tokens = [tokenizer.convert_ids_to_tokens(t) for t in input_ids]
    flat_tokens = list(chain.from_iterable(model_tokens))
    flat_str_tokens = [tokenizer.convert_tokens_to_string([t]) for t in flat_tokens]

    # Run model
    token_masks = []
    for i in range(0, len(input_ids), settings.EDITOR_BATCH_SIZE):
        batch_input_ids = tokenized["input_ids"][i: i + settings.EDITOR_BATCH_SIZE]
        batch_input_ids = torch.tensor(batch_input_ids, device=model.device)
        batch_attention_mask = tokenized["attention_mask"][i: i + settings.EDITOR_BATCH_SIZE]
        batch_attention_mask = torch.tensor(batch_attention_mask, device=model.device)
        with torch.inference_mode():
            predictions = model(batch_input_ids, attention_mask=batch_attention_mask)

        logits = predictions.logits.cpu()

        labels = logits.argmax(-1).squeeze().tolist()
        labels = list(chain.from_iterable(labels))
        token_masks.extend(labels)

    assert len(token_masks) == len(flat_tokens) == len(flat_str_tokens)

    edit_stats = defaultdict(int)
    out_tokens = []
    for i, (token, str_token, mask) in enumerate(zip(flat_tokens, flat_str_tokens, token_masks)):
        label = model.config.id2label[mask]

        match label:
            case "equal":
                out_tokens.append(str_token)
                edit_stats[label] += 1
            case "delete":
                # If we delete whitespace, roll with it, otherwise ignore
                if str_token.strip():
                    out_tokens.append(str_token)
                edit_stats[label] += 1
            case "delete_trailing_newline":
                if str_token.endswith("\n"):
                    str_token = re.sub(r"\n+$", "", str_token)
                    edit_stats[label] += 1
                out_tokens.append(str_token)

            case "delete_leading_space":
                if str_token.startswith(" "):
                    str_token = re.sub(r"^ +", "", str_token)
                    edit_stats[label] += 1
                out_tokens.append(str_token)
            case "leading_space_to_newline":
                if str_token.startswith(" "):
                    str_token = "\n" + str_token[1:]
                    edit_stats[label] += 1
                out_tokens.append(str_token)
            case "newline-1":
                out_tokens.append("\n")
                out_tokens.append(str_token)
                edit_stats[label] += 1
            case "space-1":
                out_tokens.append(" ")
                out_tokens.append(str_token)
                edit_stats[label] += 1

    return "".join(out_tokens), edit_stats






