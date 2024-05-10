from transformers import T5Config, T5PreTrainedModel
import torch
from torch import nn
from copy import deepcopy
from typing import Optional, Tuple, Union
from itertools import chain

from transformers.modeling_outputs import TokenClassifierOutput
from transformers.models.t5.modeling_t5 import T5Stack
from transformers.utils.model_parallel_utils import get_device_map, assert_device_map


def byt5_tokenize(text: str, max_length: int, pad_token_id: int = 0):
    byte_codes = []
    for char in text:
        # Add 3 to account for special tokens
        byte_codes.append([byte + 3 for byte in char.encode('utf-8')])

    tokens = list(chain.from_iterable(byte_codes))
    # Map each token to the character it represents
    char_token_lengths = [len(b) for b in byte_codes]

    batched_tokens = []
    attention_mask = []
    for i in range(0, len(tokens), max_length):
        batched_tokens.append(tokens[i:i + max_length])
        attention_mask.append([1] * len(batched_tokens[-1]))

    # Pad last item
    if len(batched_tokens[-1]) < max_length:
        batched_tokens[-1] += [pad_token_id] * (max_length - len(batched_tokens[-1]))
        attention_mask[-1] += [0] * (max_length - len(attention_mask[-1]))

    return {"input_ids": batched_tokens, "attention_mask": attention_mask, "char_token_lengths": char_token_lengths}




# From https://github.com/osainz59/t5-encoder
class T5ForTokenClassification(T5PreTrainedModel):
    _keys_to_ignore_on_load_missing = [r"encoder.embed_tokens.weight"]

    def __init__(self, config: T5Config):
        super().__init__(config)
        self.model_dim = config.d_model

        self.shared = nn.Embedding(config.vocab_size, config.d_model)

        encoder_config = deepcopy(config)
        encoder_config.is_decoder = False
        encoder_config.is_encoder_decoder = False
        encoder_config.use_cache = False
        self.encoder = T5Stack(encoder_config, self.shared)

        classifier_dropout = (
            config.classifier_dropout if hasattr(config, 'classifier_dropout') else config.dropout_rate
        )
        self.dropout = nn.Dropout(classifier_dropout)
        self.classifier = nn.Linear(config.d_model, config.num_labels)

        # Initialize weights and apply final processing
        self.post_init()

        # Model parallel
        self.model_parallel = False
        self.device_map = None


    def parallelize(self, device_map=None):
        self.device_map = (
            get_device_map(len(self.encoder.block), range(torch.cuda.device_count()))
            if device_map is None
            else device_map
        )
        assert_device_map(self.device_map, len(self.encoder.block))
        self.encoder.parallelize(self.device_map)
        self.classifier.to(self.encoder.first_device)
        self.model_parallel = True

    def deparallelize(self):
        self.encoder.deparallelize()
        self.encoder = self.encoder.to("cpu")
        self.classifier = self.classifier.to("cpu")
        self.model_parallel = False
        self.device_map = None
        torch.cuda.empty_cache()

    def get_input_embeddings(self):
        return self.shared

    def set_input_embeddings(self, new_embeddings):
        self.shared = new_embeddings
        self.encoder.set_input_embeddings(new_embeddings)

    def get_encoder(self):
        return self.encoder

    def _prune_heads(self, heads_to_prune):
        for layer, heads in heads_to_prune.items():
            self.encoder.block[layer].layer[0].SelfAttention.prune_heads(heads)

    def forward(
        self,
        input_ids: Optional[torch.LongTensor] = None,
        attention_mask: Optional[torch.FloatTensor] = None,
        head_mask: Optional[torch.FloatTensor] = None,
        inputs_embeds: Optional[torch.FloatTensor] = None,
        labels: Optional[torch.LongTensor] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None,
    ) -> Union[Tuple[torch.FloatTensor], TokenClassifierOutput]:
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict

        outputs = self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask,
            inputs_embeds=inputs_embeds,
            head_mask=head_mask,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
        )

        sequence_output = outputs[0]

        sequence_output = self.dropout(sequence_output)
        logits = self.classifier(sequence_output)

        loss = None

        if not return_dict:
            output = (logits,) + outputs[2:]
            return ((loss,) + output) if loss is not None else output

        return TokenClassifierOutput(
            loss=loss,
            logits=logits,
            hidden_states=outputs.hidden_states,
            attentions=outputs.attentions
        )