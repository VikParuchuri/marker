import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict

import click
import datasets
import tabulate
from benchmarks.overall.render import build_dataset
from tqdm import tqdm
import pypdfium2 as pdfium

from benchmarks.overall.clean import convert_to_md, clean_input
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
            gt_html = [block["html"] for block in gt_blocks if len(block["html"]) > 0]
            gt_markdown = [clean_input(convert_to_md(block)) for block in gt_html]
            scores = score_func(model_dict, sample, gt_markdown, **kwargs)
        except ValueError as e:
            print(f"Error with sample {idx}: {e}")
            continue
        except pdfium.PdfiumError as e:
            print(f"Error opening pdf: {e}")
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
        "average_score": sum([bench_scores[k]["overall_score"] for k in bench_scores]) / len(bench_scores),
    }

def print_scores(scores: Dict[str, FullResult], out_path: Path, default_method="marker"):
    inference_types = [default_method] + [k for k in scores.keys() if k != default_method]

    document_types = list(scores[default_method]["averages_by_type"].keys())
    document_rows = [[k] for k in document_types]
    for k in inference_types:
        for i, doc_type in enumerate(document_types):
            avg = sum(scores[k]["averages_by_type"][doc_type]) / max(1, len(scores[k]["averages_by_type"][doc_type]))
            document_rows[i].append(avg)

    print("Document types")
    document_type_table = tabulate.tabulate(document_rows, headers=["Document Type"] + inference_types, tablefmt="github")
    print(document_type_table)
    with open(out_path / "document_types.md", "w", encoding="utf-8") as f:
        f.write(document_type_table)

    block_types = list(scores[default_method]["averages_by_block_type"].keys())
    block_rows = [[k] for k in block_types]
    for k in inference_types:
        for i, block_type in enumerate(block_types):
            avg = sum(scores[k]["averages_by_block_type"][block_type]) / max(1, len(scores[k]["averages_by_block_type"][block_type]))
            block_rows[i].append(avg)

    print("Block types")
    block_type_table = tabulate.tabulate(block_rows, headers=["Block Type"] + inference_types, tablefmt="github")
    print(block_type_table)
    with open(out_path / "block_types.md", "w", encoding="utf-8") as f:
        f.write(block_type_table)

    headers = ["Method", "Avg Score", "Avg Time"]
    inference_rows = [[k] for k in inference_types]
    for i, k in enumerate(inference_types):
        inference_rows[i].append(scores[k]["average_score"])
        inference_rows[i].append(scores[k]["average_time"])

    print("Overall")
    overall_table = tabulate.tabulate(inference_rows, headers=headers, tablefmt="github")
    print(overall_table)
    with open(out_path / "overall.md", "w", encoding="utf-8") as f:
        f.write(overall_table)

    print("Scores computed by aligning ground truth markdown blocks with predicted markdown for each method.  The scores are 0-100 based on edit distance.")

@click.command(help="Benchmark PDF to MD conversion.")
@click.option("--dataset", type=str, help="Path to the benchmark dataset", default="datalab-to/marker_benchmark")
@click.option("--out_dataset", type=str, help="Path to the output dataset", default=None)
@click.option("--other_methods", type=str, help="Comma separated list of other methods to compare against.  Possible values: mathpix", default="")
@click.option("--result_path", type=str, default=os.path.join(settings.OUTPUT_DIR, "benchmark", "overall"), help="Output path for results.")
@click.option("--max_rows", type=int, default=None, help="Maximum number of rows to process.")
@click.option("--use_llm", is_flag=True, help="Use the LLM model for better marker quality.")
def main(
        dataset: str,
        out_dataset: str,
        other_methods: str,
        result_path: str,
        max_rows: int,
        use_llm: bool
):
    out_path = Path(result_path)
    out_path.mkdir(parents=True, exist_ok=True)

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

    # Display formatted score tables
    print_scores(all_scores, out_path)

    with open(out_path / "overall.json", "w", encoding="utf-8") as f:
        json.dump(all_scores, f, indent=2, ensure_ascii=False)

    print(f"Results saved to {out_path}.")

    # Push up comparison dataset
    if out_dataset is not None:
        out_ds = build_dataset(ds, all_scores)
        out_ds.push_to_hub(out_dataset)

if __name__ == "__main__":
    main()

