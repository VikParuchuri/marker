from pathlib import Path
from typing import Dict, List

import tabulate

from benchmarks.overall.schema import FullResult

def write_table(title: str, rows: list, headers: list, out_path: Path, filename: str):
    table = tabulate.tabulate(rows, headers=headers, tablefmt="github")
    with open(out_path / filename, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n")
        f.write(table)
    print(title)
    print(table)


def print_scores(result: FullResult, out_path: Path, methods: List[str], score_types: List[str], default_score_type="heuristic", default_method="marker"):
    document_types = list(result["averages_by_type"][default_method][default_score_type].keys())
    headers = ["Document Type"]
    for method in methods:
        for score_type in score_types:
            headers.append(f"{method} {score_type}")

    document_rows = [[k] for k in document_types]
    for i, doc_type in enumerate(document_types):
        for method in methods:
            for score_type in score_types:
                avg_score = sum(result["averages_by_type"][method][score_type][doc_type]) / max(1, len(result["averages_by_type"][method][score_type][doc_type]))
                document_rows[i].append(avg_score)

    write_table("Document Types", document_rows, headers, out_path, "document_types.md")

    headers = ["Block Type"]
    block_types = list(result["averages_by_block_type"][default_method][default_score_type].keys()) # all possible blocks
    block_score_types = list(result["averages_by_block_type"][default_method].keys())
    for method in methods:
        for score_type in block_score_types:
            headers.append(f"{method} {score_type}")

    block_rows = [[k] for k in block_types]
    for i, block_type in enumerate(block_types):
        for method in methods:
            for score_type in block_score_types:
                avg_score = sum(result["averages_by_block_type"][method][score_type][block_type]) / max(1, len(result["averages_by_block_type"][method][score_type][block_type]))
                block_rows[i].append(avg_score)

    write_table("Block types", block_rows, headers, out_path, "block_types.md")

    headers = ["Method",  "Avg Time"] + score_types
    inference_rows = [[k] for k in methods]
    all_raw_scores = [result["scores"][i] for i in result["scores"]]
    for i, method in enumerate(methods):
        avg_time = sum(result["average_times"][method]) / max(1, len(result["average_times"][method]))
        inference_rows[i].append(avg_time)
        for score_type in score_types:
            scores_lst = []
            for ar in all_raw_scores:
                try:
                    # Sometimes a few llm scores are missing
                    scores_lst.append(ar[method][score_type]["score"])
                except KeyError:
                    continue
            avg_score = sum(scores_lst) / max(1, len(scores_lst))
            inference_rows[i].append(avg_score)

    write_table("Overall Results", inference_rows, headers, out_path, "overall.md")

    print("Scores computed by aligning ground truth markdown blocks with predicted markdown for each method.  The scores are 0-100 based on edit distance.")