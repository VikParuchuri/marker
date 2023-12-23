import argparse

from marker.convert import convert_single_pdf
from marker.logger import configure_logging
from marker.models import load_all_models
import json

configure_logging()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="PDF file to parse")
    parser.add_argument("output", help="Output file name")
    parser.add_argument("--max_pages", type=int, default=None, help="Maximum number of pages to parse")
    parser.add_argument("--parallel_factor", type=int, default=1, help="How much to multiply default parallel OCR workers and model batch sizes by.")
    args = parser.parse_args()

    fname = args.filename
    model_lst = load_all_models()
    full_text, out_meta = convert_single_pdf(fname, model_lst, max_pages=args.max_pages, parallel_factor=args.parallel_factor)

    with open(args.output, "w+", encoding='utf-8') as f:
        f.write(full_text)

    out_meta_filename = args.output.rsplit(".", 1)[0] + "_meta.json"
    with open(out_meta_filename, "w+") as f:
        f.write(json.dumps(out_meta, indent=4))


if __name__ == "__main__":
    main()
