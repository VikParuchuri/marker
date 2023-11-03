import argparse

from marker.convert import convert_single_pdf
from marker.segmentation import load_layout_model
from marker.cleaners.equations import load_nougat_model
import json


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="PDF file to parse")
    parser.add_argument("output", help="Output file name")
    parser.add_argument("--max_pages", type=int, default=None, help="Maximum number of pages to parse")
    args = parser.parse_args()

    fname = args.filename
    layoutlm_model = load_layout_model()
    nougat_model = load_nougat_model()
    full_text, out_meta = convert_single_pdf(fname, layoutlm_model, nougat_model, max_pages=args.max_pages)

    with open(args.output, "w+") as f:
        f.write(full_text)

    out_meta_filename = args.output.rsplit(".", 1)[0] + "_meta.json"
    with open(out_meta_filename, "w+") as f:
        f.write(json.dumps(out_meta))