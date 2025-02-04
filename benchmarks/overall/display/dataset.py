import json
from typing import List

import datasets
from tqdm import tqdm

from benchmarks.overall.registry import METHOD_REGISTRY
from benchmarks.overall.schema import FullResult


def build_dataset(bench_dataset: datasets.Dataset, result: FullResult, score_types: List[str]) -> datasets.Dataset:
    rows = []
    for idx, sample in tqdm(enumerate(bench_dataset), desc="Building dataset"):
        if idx not in result["markdown"]:
            continue

        row = {
            "uuid": sample["uuid"],
            "classification": sample["classification"],
            "language": sample["language"],
            "img": sample["img"],
        }
        for method in result["markdown"][idx]:
            if method == "gt":
                continue

            method_cls = METHOD_REGISTRY[method]()
            md = result["markdown"][idx][method]
            method_img = method_cls.render(result["markdown"][idx][method])
            row[f"{method}_md"] = md
            row[f"{method}_img"] = method_img

            for score_type in score_types:
                row[f"{method}_{score_type}"] = result["scores"][idx][method][score_type]["score"]
                row[f"{method}_{score_type}_detail"] = json.dumps(result["scores"][idx][method][score_type]["specific_scores"])
        rows.append(row)
    ds = datasets.Dataset.from_list(rows)
    return ds

