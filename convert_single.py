import argparse

from marker.convert import convert_single_pdf
from marker.logger import configure_logging
from marker.models import load_all_models
from marker.ordering import load_ordering_model
from marker.segmentation import load_layout_model
from marker.cleaners.equations import load_nougat_model
import json

configure_logging()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="PDF file to parse")
    parser.add_argument("output", help="Output file name")
    parser.add_argument("--max_pages", type=int, default=None, help="Maximum number of pages to parse")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers to use to parallelize execution")
    args = parser.parse_args()

    fname = args.filename
    model_lst = load_all_models()
    full_text, out_meta = convert_single_pdf(fname, model_lst, max_pages=args.max_pages, parallel=args.workers)

    with open(args.output, "w+") as f:
        f.write(full_text)

    out_meta_filename = args.output.rsplit(".", 1)[0] + "_meta.json"
    with open(out_meta_filename, "w+") as f:
        f.write(json.dumps(out_meta))