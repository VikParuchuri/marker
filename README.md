# Marker

Marker converts PDF to markdown quickly and accurately.

- Supports a wide range of documents (optimized for books and scientific papers)
- Supports all languages
- Removes headers/footers/other artifacts
- Formats tables and code blocks
- Extracts and saves images along with the markdown
- Converts most equations to latex
- Works on GPU, CPU, or MPS

## How it works

Marker is a pipeline of deep learning models:

- Extract text, OCR if necessary (heuristics, [surya](https://github.com/VikParuchuri/surya), tesseract)
- Detect page layout and find reading order ([surya](https://github.com/VikParuchuri/surya))
- Clean and format each block (heuristics, [texify](https://github.com/VikParuchuri/texify)
- Combine blocks and postprocess complete text (heuristics, [pdf_postprocessor](https://huggingface.co/vikp/pdf_postprocessor_t5))

It only uses models where necessary, which improves speed and accuracy.

## Examples

| PDF                                                                   | Type        | Marker                                                                                                 | Nougat                                                                                                 |
|-----------------------------------------------------------------------|-------------|--------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| [Think Python](https://greenteapress.com/thinkpython/thinkpython.pdf) | Textbook    | [View](https://github.com/VikParuchuri/marker/blob/master/data/examples/marker/thinkpython.md)         | [View](https://github.com/VikParuchuri/marker/blob/master/data/examples/nougat/thinkpython.md)         |
| [Think OS](https://greenteapress.com/thinkos/thinkos.pdf)             | Textbook    | [View](https://github.com/VikParuchuri/marker/blob/master/data/examples/marker/thinkos.md)             | [View](https://github.com/VikParuchuri/marker/blob/master/data/examples/nougat/thinkos.md)             |
| [Switch Transformers](https://arxiv.org/pdf/2101.03961.pdf)           | arXiv paper | [View](https://github.com/VikParuchuri/marker/blob/master/data/examples/marker/switch_transformers.md) | [View](https://github.com/VikParuchuri/marker/blob/master/data/examples/nougat/switch_transformers.md) |
| [Multi-column CNN](https://arxiv.org/pdf/1804.07821.pdf)              | arXiv paper | [View](https://github.com/VikParuchuri/marker/blob/master/data/examples/marker/multicolcnn.md)         | [View](https://github.com/VikParuchuri/marker/blob/master/data/examples/nougat/multicolcnn.md)         |

## Performance

![Benchmark overall](data/images/overall.png)

The above results are with marker and nougat setup so they each take ~4GB of VRAM on an A6000.

See [below](#benchmarks) for detailed speed and accuracy benchmarks, and instructions on how to run your own benchmarks.

# Commercial usage

I want marker to be as widely accessible as possible, while still funding my development/training costs.  Research and personal usage is always okay, but there are some restrictions on commercial usage.

The weights for the models are licensed `cc-by-nc-sa-4.0`, but I will waive that for any organization under $5M USD in gross revenue in the most recent 12-month period AND under $5M in lifetime VC/angel funding raised. You also must not be competitive with the [Datalab API](https://www.datalab.to/).  If you want to remove the GPL license requirements (dual-license) and/or use the weights commercially over the revenue limit, check out the options [here](https://www.datalab.to).

# Hosted API

There's a hosted API for marker available [here](https://www.datalab.to/):

- Supports PDFs, word documents, and powerpoints 
- 1/4th the price of leading cloud-based competitors
- High uptime (99.99%), quality, and speed (.25s/page for 50 page doc)

# Community

[Discord](https://discord.gg//KuZwXNGnfH) is where we discuss future development.

# Limitations

PDF is a tricky format, so marker will not always work perfectly.  Here are some known limitations that are on the roadmap to address:

- Marker will not convert 100% of equations to LaTeX.  This is because it has to detect then convert.
- Tables are not always formatted 100% correctly - text can be in the wrong column.
- Whitespace and indentations are not always respected.
- Not all lines/spans will be joined properly.
- This works best on digital PDFs that won't require a lot of OCR.  It's optimized for speed, and limited OCR is used to fix errors.

# Installation

You'll need python 3.9+ and PyTorch.  You may need to install the CPU version of torch first if you're not using a Mac or a GPU machine.  See [here](https://pytorch.org/get-started/locally/) for more details.

Install with:

```shell
pip install marker-pdf
```

## Optional: OCRMyPDF

Only needed if you want to use the optional `ocrmypdf` as the ocr backend.  Note that `ocrmypdf` includes Ghostscript, an AGPL dependency, but calls it via CLI, so it does not trigger the license provisions.

See the instructions [here](docs/install_ocrmypdf.md)

# Usage

First, some configuration:

- Inspect the settings in `marker/settings.py`.  You can override any settings with environment variables.
- Your torch device will be automatically detected, but you can override this.  For example, `TORCH_DEVICE=cuda`.
- By default, marker will use `surya` for OCR.  Surya is slower on CPU, but more accurate than tesseract.  It also doesn't require you to specify the languages in the document.  If you want faster OCR, set `OCR_ENGINE` to `ocrmypdf`. This also requires external dependencies (see above).  If you don't want OCR at all, set `OCR_ENGINE` to `None`.
- Some PDFs, even digital ones, have bad text in them.  Set `OCR_ALL_PAGES=true` to force OCR if you find bad output from marker.

## Interactive App

I've included a streamlit app that lets you interactively try marker with some basic options.  Run it with:

```shell
pip install streamlit
marker_gui
```

## Convert a single file

```shell
marker_single /path/to/file.pdf /path/to/output/folder --batch_multiplier 2 --max_pages 10 
```

- `--batch_multiplier` is how much to multiply default batch sizes by if you have extra VRAM.  Higher numbers will take more VRAM, but process faster.  Set to 2 by default.  The default batch sizes will take ~3GB of VRAM.
- `--max_pages` is the maximum number of pages to process.  Omit this to convert the entire document.
- `--start_page` is the page to start from (default is None, will start from the first page).
- `--langs` is an optional comma separated list of the languages in the document, for OCR.  Optional by default, required if you use tesseract.

The list of supported languages for surya OCR is [here](https://github.com/VikParuchuri/surya/blob/master/surya/languages.py).  If you need more languages, you can use any language supported by [Tesseract](https://tesseract-ocr.github.io/tessdoc/Data-Files#data-files-for-version-400-november-29-2016) if you set `OCR_ENGINE` to `ocrmypdf`.  If you don't need OCR, marker can work with any language.

## Convert multiple files

```shell
marker /path/to/input/folder /path/to/output/folder --workers 4 --max 10
```

- `--workers` is the number of pdfs to convert at once.  This is set to 1 by default, but you can increase it to increase throughput, at the cost of more CPU/GPU usage.  Marker will use 5GB of VRAM per worker at the peak, and 3.5GB average.
- `--max` is the maximum number of pdfs to convert.  Omit this to convert all pdfs in the folder.
- `--min_length` is the minimum number of characters that need to be extracted from a pdf before it will be considered for processing.  If you're processing a lot of pdfs, I recommend setting this to avoid OCRing pdfs that are mostly images. (slows everything down)
- `--metadata_file` is an optional path to a json file with metadata about the pdfs.  If you provide it, it will be used to set the language for each pdf.  Setting language is optional for surya (default), but required for tesseract. The format is:

```
{
  "pdf1.pdf": {"languages": ["English"]},
  "pdf2.pdf": {"languages": ["Spanish", "Russian"]},
  ...
}
```

You can use language names or codes.  The exact codes depend on the OCR engine.  See [here](https://github.com/VikParuchuri/surya/blob/master/surya/languages.py) for a full list for surya codes, and [here](https://tesseract-ocr.github.io/tessdoc/Data-Files#data-files-for-version-400-november-29-2016) for tesseract.

## Convert multiple files on multiple GPUs

```shell
METADATA_FILE=../pdf_meta.json NUM_DEVICES=4 NUM_WORKERS=15 marker_chunk_convert ../pdf_in ../md_out
```

- `METADATA_FILE` is an optional path to a json file with metadata about the pdfs.  See above for the format.
- `NUM_DEVICES` is the number of GPUs to use.  Should be `2` or greater.
- `NUM_WORKERS` is the number of parallel processes to run on each GPU.
- `MIN_LENGTH` is the minimum number of characters that need to be extracted from a pdf before it will be considered for processing.  If you're processing a lot of pdfs, I recommend setting this to avoid OCRing pdfs that are mostly images. (slows everything down)

Note that the env variables above are specific to this script, and cannot be set in `local.env`.


## Use from python

See the `convert_single_pdf` function for additional arguments that can be passed.

```python
from marker.convert import convert_single_pdf
from marker.models import load_all_models

fpath = "FILEPATH"
model_lst = load_all_models()
full_text, images, out_meta = convert_single_pdf(fpath, model_lst)
```

# Output format

The output will be a markdown file, but there will also be a metadata json file that gives information about the conversion process.  It has these fields:

```json
{
    "languages": null, // any languages that were passed in
    "filetype": "pdf", // type of the file
    "pdf_toc": [], // the table of contents from the pdf
    "computed_toc": [], //the computed table of contents
    "pages": 10, // page count
    "ocr_stats": {
        "ocr_pages": 0, // number of pages OCRed
        "ocr_failed": 0, // number of pages where OCR failed
        "ocr_success": 0,
        "ocr_engine": "none"
    },
    "block_stats": {
        "header_footer": 0,
        "code": 0, // number of code blocks
        "table": 2, // number of tables
        "equations": {
            "successful_ocr": 0,
            "unsuccessful_ocr": 0,
            "equations": 0
        }
    }
}
```

## API server

There is a very simple API server you can run like this:

```shell
pip install -U uvicorn fastapi python-multipart
marker_server --port 8001
```

This will start a fastapi server that you can access at `localhost:8001`.  You can go to `localhost:8001/docs` to see the endpoint options.

Note that this is not a very robust API, and is only intended for small-scale use.  If you want to use this server, but want a more robust conversion option, you can run against the hosted [Datalab API](https://www.datalab.to/plans).  You'll need to register and get an API key, then run:

```shell
marker_server --port 8001 --api_key API_KEY
```

Note: This is not the recommended way to use the Datalab API - it's only provided as a convenience for people wrapping the marker repo.  The recommended way is to make a post request to the endpoint directly from your code vs proxying through this server.

You can send requests like this:

```
import requests
import json

post_data = {
    'filepath': 'FILEPATH',
    # Add other params here
}

requests.post("http://localhost:8001/marker", data=json.dumps(post_data)).json()
```

# Troubleshooting

There are some settings that you may find useful if things aren't working the way you expect:

- `OCR_ALL_PAGES` - set this to true to force OCR all pages.  This can be very useful if there is garbled text in the output of marker.
- `TORCH_DEVICE` - set this to force marker to use a given torch device for inference.
- `OCR_ENGINE` - can set this to `surya` or `ocrmypdf`.
- Verify that you set the languages correctly, or passed in a metadata file.
- If you're getting out of memory errors, decrease worker count (increased the `VRAM_PER_TASK` setting).  You can also try splitting up long PDFs into multiple files.

In general, if output is not what you expect, trying to OCR the PDF is a good first step.  Not all PDFs have good text/bboxes embedded in them.

## Debugging

Set `DEBUG=true` to save data to the `debug` subfolder in the marker root directory.  This will save images of each page with detected layout and text, as well as output a json file with additional bounding box information.

## Useful settings

These settings can improve/change output quality:

- `OCR_ALL_PAGES` will force OCR across the document.  Many PDFs have bad text embedded due to older OCR engines being used.
- `PAGINATE_OUTPUT` will put a horizontal rule between pages.  Default: False.  The horizontal rule will be `\n\n`, then `{PAGE_NUMBER}`, then 48 single dashes `-`, then `\n\n`.  The separator can be configured via the `PAGE_SEPARATOR` setting.
- `EXTRACT_IMAGES` will extract images and save separately.  Default: True.
- `BAD_SPAN_TYPES` specifies layout blocks to remove from the markdown output.

# Benchmarks

Benchmarking PDF extraction quality is hard.  I've created a test set by finding books and scientific papers that have a pdf version and a latex source.  I convert the latex to text, and compare the reference to the output of text extraction methods.  It's noisy, but at least directionally correct.

Benchmarks show that marker is 4x faster than nougat, and more accurate outside arXiv (nougat was trained on arXiv data).  We show naive text extraction (pulling text out of the pdf with no processing) for comparison.

**Speed**

| Method | Average Score | Time per page | Time per document |
|--------|---------------|---------------|-------------------|
| marker | 0.613721      | 0.631991      | 58.1432           |
| nougat | 0.406603      | 2.59702       | 238.926           |

**Accuracy**

First 3 are non-arXiv books, last 3 are arXiv papers.

| Method | multicolcnn.pdf | switch_trans.pdf | thinkpython.pdf | thinkos.pdf | thinkdsp.pdf | crowd.pdf |
|--------|-----------------|------------------|-----------------|-------------|--------------|-----------|
| marker | 0.536176        | 0.516833         | 0.70515         | 0.710657    | 0.690042     | 0.523467  |
| nougat | 0.44009         | 0.588973         | 0.322706        | 0.401342    | 0.160842     | 0.525663  |

Peak GPU memory usage during the benchmark is `4.2GB` for nougat, and `4.1GB` for marker.  Benchmarks were run on an A6000 Ada.

**Throughput**

Marker takes about 4GB of VRAM on average per task, so you can convert 12 documents in parallel on an A6000.

![Benchmark results](data/images/per_doc.png)

## Running your own benchmarks

You can benchmark the performance of marker on your machine. Install marker manually with:

```shell
git clone https://github.com/VikParuchuri/marker.git
poetry install
```

Download the benchmark data [here](https://drive.google.com/file/d/1ZSeWDo2g1y0BRLT7KnbmytV2bjWARWba/view?usp=sharing) and unzip. Then run the overall benchmark like this:

```shell
python benchmarks/overall.py data/pdfs data/references report.json --nougat
```

This will benchmark marker against other text extraction methods.  It sets up batch sizes for nougat and marker to use a similar amount of GPU RAM for each.

Omit `--nougat` to exclude nougat from the benchmark.  I don't recommend running nougat on CPU, since it is very slow.

# Thanks

This work would not have been possible without amazing open source models and datasets, including (but not limited to):

- Surya
- Texify
- Pypdfium2/pdfium
- DocLayNet from IBM

Thank you to the authors of these models and datasets for making them available to the community!