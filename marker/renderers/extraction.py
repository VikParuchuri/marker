from dataclasses import dataclass
from typing import Dict

from pydantic import BaseModel

from marker.extractors import ExtractionResult
from marker.renderers import BaseRenderer


@dataclass
class MergeData:
    confidence_exists_1: float
    confidence_exists_2: float
    confidence_value_1: float
    confidence_value_2: float


def merge_keys(
    json: dict | list, json2: dict, merge_data: MergeData, confidence_threshold: int = 3
):
    if isinstance(json, list):
        json.extend(json2)

    elif isinstance(json, dict):
        for key in json:
            if isinstance(json[key], dict):
                merge_keys(json[key], json2[key], merge_data)
            elif isinstance(json[key], list):
                json[key] = json[key] + json2[key]
            else:
                value_2_correct = (
                    merge_data.confidence_exists_2 > confidence_threshold
                    and merge_data.confidence_value_2 > confidence_threshold
                )

                if value_2_correct and json2[key]:
                    json[key] = json2[key]

                if not json[key] and json2[key]:
                    json[key] = json2[key]


class ExtractionOutput(BaseModel):
    pages: Dict[int, ExtractionResult]
    document_json: dict


class ExtractionRenderer(BaseRenderer):
    def __call__(self, outputs: Dict[int, ExtractionResult]) -> ExtractionOutput:
        pnums = sorted(list(outputs.keys()))
        merged_result = outputs[pnums[0]].extracted_data.copy()
        confidence_exists = outputs[pnums[0]].existence_confidence
        confidence_value = outputs[pnums[0]].value_confidence

        for pnum in pnums[1:]:
            merge_data = MergeData(
                confidence_exists_1=confidence_exists,
                confidence_exists_2=outputs[pnum].existence_confidence,
                confidence_value_1=confidence_value,
                confidence_value_2=outputs[pnum].value_confidence,
            )
            merge_keys(merged_result, outputs[pnum].extracted_data, merge_data)

        return ExtractionOutput(pages=outputs, document_json=merged_result)
