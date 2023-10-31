import argparse

from marker.convert import convert_single_pdf
from marker.segmentation import load_layout_model
from marker.cleaners.equations import load_nougat_model


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="PDF file to parse")
    parser.add_argument("output", help="Output file name")
    args = parser.parse_args()

    fname = args.filename
    layoutlm_model = load_layout_model()
    nougat_model = load_nougat_model()
    full_text = convert_single_pdf(fname, layoutlm_model, nougat_model)

    with open(args.output, "w+") as f:
        f.write(full_text)