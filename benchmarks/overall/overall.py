import json
import os
import traceback
from collections import defaultdict
from pathlib import Path
from typing import List

import click
import datasets
import torch
from tqdm import tqdm

from benchmarks.overall.display.dataset import build_dataset
from benchmarks.overall.registry import SCORE_REGISTRY, METHOD_REGISTRY
from benchmarks.overall.schema import FullResult
from marker.logger import configure_logging
from marker.models import create_model_dict
from marker.settings import settings
from benchmarks.overall.display.table import print_scores

configure_logging()


def get_method_scores(benchmark_dataset: datasets.Dataset, methods: List[str], score_types: List[str], artifacts: dict, max_rows=None) -> FullResult:
    bench_scores = {}
    averages_by_type = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    averages_by_block_type = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    average_times = defaultdict(list)
    markdown_by_method = defaultdict(dict)
    total_rows = len(benchmark_dataset)
    if max_rows:
        total_rows = min(max_rows, total_rows)
    for idx, sample in tqdm(enumerate(benchmark_dataset), desc="Running benchmark", total=total_rows):
        if max_rows is not None and idx >= max_rows:
            break

        doc_type = sample["classification"]
        gt_cls = METHOD_REGISTRY["gt"]
        gt_blocks = json.loads(sample["gt_blocks"])
        gt_md = gt_cls(**artifacts)(sample)["markdown"]
        markdown_by_method[idx]["gt"] = gt_md

        out_data = defaultdict(dict)

        try:
            for method in methods:
                method_cls = METHOD_REGISTRY[method](**artifacts)
                method_info = method_cls(sample)
                method_md = method_info["markdown"]
                if method_md is None:
                    method_md = "" # Avoid None values

                average_times[method].append(method_info["time"])
                markdown_by_method[idx][method] = method_md

                for score_type in score_types:
                    score_cls = SCORE_REGISTRY[score_type]()
                    try:
                        scores = score_cls(sample, gt_md, method_md)
                    except Exception as e:
                        # Some scorers can fail, like the LLM one
                        print(f"Failed to score {method} with {score_type}: {e}")
                        continue

                    out_data[method][score_type] = scores

                    averages_by_type[method][score_type][doc_type].append(scores["score"])

                    if "by_block" in scores["specific_scores"]: # Not all scorers support this
                        for score, gt_block in zip(scores["specific_scores"]["by_block"], gt_blocks):
                            averages_by_block_type[method][score_type][gt_block["block_type"]].append(score)
        except Exception as e:
            print(f"Failed to process {idx}: {e}")
            traceback.print_exc()
            if idx in markdown_by_method:
                del markdown_by_method[idx]
            continue

        bench_scores[idx] = out_data

    return {
        "scores": bench_scores,
        "markdown": markdown_by_method,
        "averages_by_type": averages_by_type,
        "averages_by_block_type": averages_by_block_type,
        "average_times": average_times,
    }

@click.command(help="Benchmark PDF to MD conversion.")
@click.option("--dataset", type=str, help="Path to the benchmark dataset", default="datalab-to/marker_benchmark")
@click.option("--out_dataset", type=str, help="Path to the output dataset", default=None)
@click.option("--methods", type=str, help="Comma separated list of other methods to compare against.  Possible values: marker,mathpix,llamaparse,docling,mistral", default="marker")
@click.option("--scores", type=str, help="Comma separated list of scoring functions to use.  Possible values: heuristic,llm", default="heuristic")
@click.option("--result_path", type=str, default=os.path.join(settings.OUTPUT_DIR, "benchmark", "overall"), help="Output path for results.")
@click.option("--max_rows", type=int, default=None, help="Maximum number of rows to process.")
@click.option("--use_llm", is_flag=True, help="Use the LLM model for better marker quality.")
@click.option("--languages", type=str, help="Comma separated list of languages to use for LLM", default=None)
def main(
        dataset: str,
        out_dataset: str,
        methods: str,
        scores: str,
        result_path: str,
        max_rows: int,
        use_llm: bool,
        languages: str
):
    out_path = Path(result_path)
    out_path.mkdir(parents=True, exist_ok=True)

    methods = methods.split(",")
    for method in methods:
        if method not in METHOD_REGISTRY:
            raise ValueError(f"Method {method} not allowed.  Allowed methods are {METHOD_REGISTRY.keys()}")

    # Ensure marker is always first
    all_methods = list(set(methods))
    methods = ["marker"] if "marker" in all_methods else []
    methods += [m for m in all_methods if m != "marker"]

    score_types = scores.split(",")
    for score_type in score_types:
        if score_type not in SCORE_REGISTRY:
            raise ValueError(f"Score type {score_type} not allowed.  Allowed types are {SCORE_REGISTRY.keys()}")

    if languages:
        languages = languages.split(",")
    else:
        languages = None

    benchmark_dataset = datasets.load_dataset(dataset, split="train")
    if languages:
        benchmark_dataset = benchmark_dataset.filter(lambda x: x["language"] in languages)

    artifacts = {
        "model_dict": create_model_dict(),
        "use_llm": use_llm,
        "mathpix_ds": None,
        "llamaparse_ds": None,
    }

    if "mathpix" in methods:
        artifacts["mathpix_ds"] = datasets.load_dataset("datalab-to/marker_benchmark_mathpix", split="train")

    if "llamaparse" in methods:
        artifacts["llamaparse_ds"] = datasets.load_dataset("datalab-to/marker_benchmark_llamaparse", split="train")

    if "mistral" in methods:
        artifacts["mistral_ds"] = datasets.load_dataset("datalab-to/marker_benchmark_mistral", split="train")

    if "olmocr" in methods:
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
        model = Qwen2VLForConditionalGeneration.from_pretrained("allenai/olmOCR-7B-0225-preview",
                                                                torch_dtype=torch.bfloat16).eval()
        processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-7B-Instruct")
        model.to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        artifacts["olmocr_model"] = {"model": model, "processor": processor}

    print(f"Running benchmark with methods: {methods} and scores: {score_types}")
    result = get_method_scores(benchmark_dataset, methods, score_types, artifacts, max_rows=max_rows)

    # Display benchmark scoring tables
    print_scores(result, out_path, methods, score_types, default_method=methods[0], default_score_type=score_types[0])

    # Write to json
    with open(out_path / "result.json", "w") as f:
        json.dump(result, f)

    if out_dataset:
        if use_llm:
            out_dataset += "_llm"
        dataset = build_dataset(benchmark_dataset, result, score_types, max_rows=max_rows)
        dataset.push_to_hub(out_dataset, private=True)


if __name__ == "__main__":
    main()

