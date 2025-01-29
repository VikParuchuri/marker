import json
import os
from collections import defaultdict
from pathlib import Path

import click
import datasets
import tabulate
from tqdm import tqdm

from marker.logger import configure_logging
from marker.models import create_model_dict
from inference import get_marker_block_html
from marker.settings import settings
from scoring import score_blocks

configure_logging()

@click.command(help="Benchmark PDF to MD conversion.")
@click.option("--dataset", type=str, help="Path to the benchmark dataset", default="datalab-to/marker_benchmark")
@click.option("--other_methods", type=str, help="Comma separated list of other methods to compare against.  Possible values:", default="")
@click.option("--result_path", type=str, default=os.path.join(settings.OUTPUT_DIR, "benchmark", "overall"), help="Output path for results.")
@click.option("--max_rows", type=int, default=None, help="Maximum number of rows to process.")
def main(
        dataset: str,
        other_methods: str,
        result_path: str,
        max_rows: int
):
    allowed_methods = [""]
    methods = other_methods.split(",")
    for method in methods:
        if method not in allowed_methods:
            raise ValueError(f"Method {method} not allowed.  Allowed methods are {allowed_methods}")

    model_dict = create_model_dict()
    ds = datasets.load_dataset(dataset, split="train")

    bench_scores = {}
    averages_by_type = defaultdict(list)
    averages_by_block_type = defaultdict(list)
    for idx, sample in tqdm(enumerate(ds), desc="Running benchmark"):
        gt_blocks = json.loads(sample["gt_blocks"])
        doc_type = sample["classification"]
        pdf_bytes = sample["pdf"] # This is a single page PDF
        marker_html = get_marker_block_html(model_dict, gt_blocks, pdf_bytes)
        gt_html = [block["html"] for block in gt_blocks]
        scores = score_blocks(gt_html, marker_html)
        gt_weights = [len(ht) for ht in gt_html]
        overall_score = sum([s * w for s, w in zip(scores, gt_weights)]) / sum(gt_weights)
        bench_scores[idx] = {
            "scores": scores,
            "weights": gt_weights,
            "overall_score": overall_score # Weighted score, weighted by length of GT block
        }

        averages_by_type[doc_type].append(overall_score)

        for score, gt_block in zip(scores, gt_blocks):
            averages_by_block_type[gt_block["block_type"]].append(score)

        if max_rows is not None and idx >= max_rows:
            break

    for k in averages_by_type:
        averages_by_type[k] = sum(averages_by_type[k]) / len(averages_by_type[k])
    averages_by_type = sorted(averages_by_type.items())

    print(tabulate.tabulate(averages_by_type, headers=["Document Type", "Average Score"], tablefmt="github"))

    for k in averages_by_block_type:
        averages_by_block_type[k] = sum(averages_by_block_type[k]) / len(averages_by_block_type[k])
    averages_by_block_type = sorted(averages_by_block_type.items())

    print(tabulate.tabulate(averages_by_block_type, headers=["Block Type", "Average Score"], tablefmt="github"))

    overall_average = sum([bench_scores[k]["overall_score"] for k in bench_scores]) / len(bench_scores)
    print(tabulate.tabulate([["Overall Average", overall_average]], tablefmt="github"))

    out_path = Path(result_path) / "overall.json"
    with open(out_path, "w") as f:
        json.dump(bench_scores, f, indent=2)

    print(f"Results saved to {out_path}.")

if __name__ == "__main__":
    main()

