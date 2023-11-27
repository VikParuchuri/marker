import argparse
import tempfile
import time
from collections import defaultdict

from tqdm import tqdm

from marker.convert import convert_single_pdf
from marker.logger import configure_logging
from marker.ordering import load_ordering_model
from marker.segmentation import load_layout_model
from marker.cleaners.equations import load_nougat_model
from marker.benchmark.scoring import score_text
from marker.extract_text import naive_get_text
import json
import os
import subprocess
import shutil
import fitz as pymupdf
from marker.settings import settings
from tabulate import tabulate

configure_logging()


def nougat_prediction(pdf_filename, batch_size=2):
    out_dir = tempfile.mkdtemp()
    # No skipping avoids failure detection, so we attempt to convert the full doc
    # Batch size 2 is to match VRAM usage of marker
    subprocess.run(["nougat", pdf_filename, "-o", out_dir, "--no-skipping", "--recompute", "--batchsize", str(batch_size)], check=True)
    md_file = os.listdir(out_dir)[0]
    with open(os.path.join(out_dir, md_file), "r") as f:
        data = f.read()
    shutil.rmtree(out_dir)
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark PDF to MD conversion.  Needs source pdfs, and a refernece folder with the correct markdown.")
    parser.add_argument("in_folder", help="Input PDF files")
    parser.add_argument("reference_folder", help="Reference folder with reference markdown files")
    parser.add_argument("out_file", help="Output filename")
    parser.add_argument("--nougat", action="store_true", help="Run nougat and compare", default=False)
    parser.add_argument("--nougat_batch_size", type=int, default=settings.NOUGAT_BATCH_SIZE, help="Batch size to use for nougat when making predictions.")
    parser.add_argument("--marker_parallel", type=int, default=4, help="Number of marker CPU processes to run in parallel")
    parser.add_argument("--md_out_path", type=str, default=None, help="Output path for generated markdown files")
    args = parser.parse_args()

    methods = ["naive", "marker"]
    if args.nougat:
        methods.append("nougat")

    layoutlm_model = load_layout_model()
    nougat_model = load_nougat_model()
    order_model = load_ordering_model()

    scores = defaultdict(dict)
    benchmark_files = os.listdir(args.in_folder)
    benchmark_files = [b for b in benchmark_files if b.endswith(".pdf")]
    times = defaultdict(int)

    for fname in tqdm(benchmark_files):
        md_filename = fname.rsplit(".", 1)[0] + ".md"

        reference_filename = os.path.join(args.reference_folder, md_filename)
        with open(reference_filename, "r") as f:
            reference = f.read()

        pdf_filename = os.path.join(args.in_folder, fname)
        doc = pymupdf.open(pdf_filename)

        for method in methods:
            start = time.time()
            if method == "marker":
                full_text, out_meta = convert_single_pdf(pdf_filename, layoutlm_model, nougat_model, order_model, parallel=args.marker_parallel)
            elif method == "nougat":
                full_text = nougat_prediction(pdf_filename, batch_size=args.nougat_batch_size)
            elif method == "naive":
                full_text = naive_get_text(doc)
            else:
                raise ValueError(f"Unknown method {method}")

            times[method] += time.time() - start

            score = score_text(full_text, reference)
            scores[method][fname] = score

            if args.md_out_path:
                md_out_filename = f"{method}_{md_filename}"
                with open(os.path.join(args.md_out_path, md_out_filename), "w+") as f:
                    f.write(full_text)

    with open(args.out_file, "w+") as f:
        write_data = defaultdict(dict)
        for method in methods:
            write_data[method] = {
                "avg_score": sum(scores[method].values()) / len(scores[method]),
                "scores": scores[method],
                "time_per_doc": times[method] / len(scores[method])
            }

        json.dump(write_data, f, indent=4)

    summary_table = []
    score_table = []
    score_headers = benchmark_files
    for method in methods:
        summary_table.append([method, write_data[method]["avg_score"], write_data[method]["time_per_doc"]])
        score_table.append([method, *[write_data[method]["scores"][h] for h in score_headers]])

    print(tabulate(summary_table, headers=["Method", "Average Score", "Time per doc"]))
    print("")
    print("Scores by file")
    print(tabulate(score_table, headers=["Method", *score_headers]))
