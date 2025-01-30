import json
import os
import traceback
from collections import defaultdict
from pathlib import Path

import click
import datasets
import tabulate
from tqdm import tqdm

from benchmarks.overall.inference import marker_scoring_func, mathpix_scoring_func
from benchmarks.overall.schema import FullResult
from marker.logger import configure_logging
from marker.models import create_model_dict
from marker.settings import settings

configure_logging()


def get_method_scores(ds, model_dict, max_rows=None, score_func=marker_scoring_func, **kwargs) -> FullResult:
    bench_scores = {}
    averages_by_type = defaultdict(list)
    averages_by_block_type = defaultdict(list)
    for idx, sample in tqdm(enumerate(ds), desc="Running benchmark"):
        if max_rows is not None and idx >= max_rows:
            break

        gt_blocks = json.loads(sample["gt_blocks"])
        doc_type = sample["classification"]
        try:
            gt_html = [block["html"] for block in gt_blocks]
            scores = score_func(model_dict, sample, gt_html, **kwargs)
        except ValueError as e:
            print(f"Error with sample {idx}: {e}")
            continue
        averages_by_type[doc_type].append(scores["overall_score"])

        for score, gt_block in zip(scores["scores"], gt_blocks):
            averages_by_block_type[gt_block["block_type"]].append(score)

        bench_scores[idx] = scores

    avg_time = sum([bench_scores[k]["time"] for k in bench_scores]) / len(bench_scores)
    return {
        "raw_scores": bench_scores,
        "averages_by_type": averages_by_type,
        "averages_by_block_type": averages_by_block_type,
        "average_time": avg_time,
        "average_score": sum([bench_scores[k]["overall_score"] for k in bench_scores]) / len(bench_scores)
    }

def print_scores(scores: FullResult, method: str):
    averages_by_type = scores["averages_by_type"]
    averages_by_block_type = scores["averages_by_block_type"]
    bench_scores = scores["raw_scores"]

    for k in averages_by_type:
        averages_by_type[k] = sum(averages_by_type[k]) / len(averages_by_type[k])
    averages_by_type = sorted(averages_by_type.items())

    print(f"Scores for method {method}:")
    print(tabulate.tabulate(averages_by_type, headers=["Document Type", "Average Score"], tablefmt="github"))

    for k in averages_by_block_type:
        averages_by_block_type[k] = sum(averages_by_block_type[k]) / len(averages_by_block_type[k])
    averages_by_block_type = sorted(averages_by_block_type.items())

    print(tabulate.tabulate(averages_by_block_type, headers=["Block Type", "Average Score"], tablefmt="github"))

    overall_average = sum([bench_scores[k]["overall_score"] for k in bench_scores]) / len(bench_scores)
    print(tabulate.tabulate([["Overall Average", overall_average]], tablefmt="github"))
    print()

@click.command(help="Benchmark PDF to MD conversion.")
@click.option("--dataset", type=str, help="Path to the benchmark dataset", default="datalab-to/marker_benchmark")
@click.option("--other_methods", type=str, help="Comma separated list of other methods to compare against.  Possible values: mathpix", default="")
@click.option("--result_path", type=str, default=os.path.join(settings.OUTPUT_DIR, "benchmark", "overall"), help="Output path for results.")
@click.option("--max_rows", type=int, default=None, help="Maximum number of rows to process.")
@click.option("--use_llm", is_flag=True, help="Use the LLM model for better marker quality.")
def main(
        dataset: str,
        other_methods: str,
        result_path: str,
        max_rows: int,
        use_llm: bool
):
    allowed_methods = ["mathpix", ""]
    methods = other_methods.split(",")
    for method in methods:
        if method not in allowed_methods:
            raise ValueError(f"Method {method} not allowed.  Allowed methods are {allowed_methods}")

    model_dict = create_model_dict()
    ds = datasets.load_dataset(dataset, split="train")

    marker_scores = get_method_scores(ds, model_dict, max_rows=max_rows, use_llm=use_llm)
    all_scores = {
        "marker": marker_scores
    }

    if "mathpix" in methods:
        mathpix_ds = datasets.load_dataset("datalab-to/marker_benchmark_mathpix", split="train")
        mathpix_scores = get_method_scores(ds, model_dict, max_rows=max_rows, score_func=mathpix_scoring_func, mathpix_ds=mathpix_ds)
        all_scores["mathpix"] = mathpix_scores

    for k,v in all_scores.items():
        print_scores(v, k)

    out_path = Path(result_path)
    out_path.mkdir(parents=True, exist_ok=True)
    with open(out_path / "overall.json", "w", encoding="utf-8") as f:
        json.dump(all_scores, f, indent=2, ensure_ascii=False)

    print(f"Results saved to {out_path}.")

if __name__ == "__main__":
    main()

