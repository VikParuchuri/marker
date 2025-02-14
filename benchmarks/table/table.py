import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"  # Transformers uses .isin for an op, which is not supported on MPS

from pathlib import Path
from itertools import repeat
from typing import List

import time
import datasets
from tqdm import tqdm
import click
from tabulate import tabulate
import json
from concurrent.futures import ProcessPoolExecutor

from marker.settings import settings
from benchmarks.table.inference import inference_tables

from scoring import wrap_table_html, similarity_eval_html

def update_teds_score(result, prefix: str = "marker"):
    prediction, ground_truth = result[f'{prefix}_table'], result['gt_table']
    prediction, ground_truth = wrap_table_html(prediction), wrap_table_html(ground_truth)
    score = similarity_eval_html(prediction, ground_truth)
    result.update({f'{prefix}_score':score})
    return result


@click.command(help="Benchmark Table to HTML Conversion")
@click.option("--result_path", type=str, default=os.path.join(settings.OUTPUT_DIR, "benchmark", "table"), help="Output path for results.")
@click.option("--dataset", type=str, default="datalab-to/fintabnet_bench_marker", help="Dataset to use")
@click.option("--max_rows", type=int, default=None, help="Maximum number of PDFs to process")
@click.option("--max_workers", type=int, default=16, help="Maximum number of workers to use")
@click.option("--use_llm", is_flag=True, help="Use LLM for improving table recognition.")
@click.option("--table_rec_batch_size", type=int, default=None, help="Batch size for table recognition.")
@click.option("--use_gemini", is_flag=True, help="Evaluate Gemini for table recognition.")
def main(
        result_path: str,
        dataset: str,
        max_rows: int,
        max_workers: int,
        use_llm: bool,
        table_rec_batch_size: int | None,
        use_gemini: bool = False
):
    start = time.time()


    dataset = datasets.load_dataset(dataset, split='train')
    dataset = dataset.shuffle(seed=0)

    results, total_unaligned = inference_tables(dataset, use_llm, table_rec_batch_size, max_rows, use_gemini)

    print(f"Total time: {time.time() - start}.")
    print(f"Could not align {total_unaligned} tables from fintabnet.")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        marker_results = list(
            tqdm(
                executor.map(update_teds_score, results), desc='Computing alignment scores', total=len(results)
            )
        )

    avg_score = sum([r["marker_score"] for r in marker_results]) / len(marker_results)
    headers = ["Avg score", "Total tables"]
    data = [f"{avg_score:.3f}", len(marker_results)]
    gemini_results = None
    if use_gemini:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            gemini_results = list(
                tqdm(
                    executor.map(update_teds_score, results, repeat("gemini")), desc='Computing Gemini scores',
                    total=len(results)
                )
            )
        avg_gemini_score = sum([r["gemini_score"] for r in gemini_results]) / len(gemini_results)
        headers.append("Avg Gemini score")
        data.append(f"{avg_gemini_score:.3f}")

    table = tabulate([data], headers=headers, tablefmt="github")
    print(table)
    print("Avg score computed by comparing marker predicted HTML with original HTML")

    results = {
        "marker": marker_results,
        "gemini": gemini_results
    }

    out_path = Path(result_path)
    out_path.mkdir(parents=True, exist_ok=True)
    with open(out_path / "table.json", "w+") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to {out_path}.")

if __name__ == '__main__':
    main()