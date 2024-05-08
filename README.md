# Marker

Marker converts PDF to markdown.  It's 10x faster than nougat, more accurate on most documents, and has low hallucination risk.

- Support for a range of documents (optimized for books and scientific papers)
- Removes headers/footers/other artifacts
- Converts most equations to latex
- Formats tables and code blocks
- Support for all languages (although most testing is done in English).
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

The above results are with marker and nougat setup so they each take ~3GB of VRAM on an A6000.

See [below](#benchmarks) for detailed speed and accuracy benchmarks, and instructions on how to run your own benchmarks.

# Community

[Discord](https://discord.gg//KuZwXNGnfH) is where we discuss future development.

# Limitations

PDF is a tricky format, so marker will not always work perfectly.  Here are some known limitations that are on the roadmap to address:

- Marker will not convert 100% of equations to LaTeX.  This is because it has to detect then convert.
- Whitespace and indentations are not always respected.
- Not all lines/spans will be joined properly.
- This works best on digital PDFs that won't require a lot of OCR.  It's optimized for speed, and limited OCR is used to fix errors.

# Installation

This has been tested on Mac and Linux (Ubuntu and Debian).  You'll need python 3.9+ and [poetry](https://python-poetry.org/docs/#installing-with-the-official-installer).

First, clone the repo:

- `git clone https://github.com/VikParuchuri/marker.git`
- `cd marker`

## Linux

- Install python requirements
  - `poetry install`
  - `poetry shell` to activate your poetry venv
- Update pytorch since poetry doesn't play nicely with it
  - GPU only: run `pip install torch` to install other torch dependencies.
  - CPU only: Uninstall torch with `poetry remove torch`, then follow the [CPU install](https://pytorch.org/get-started/locally/) instructions.

**Optional**

Only needed if using `ocrmypdf` as the ocr backend.

- Run `pip install ocrmypdf`
- Install ghostscript > 9.55 by following [these instructions](https://ghostscript.readthedocs.io/en/latest/Install.html) or running `scripts/install/ghostscript_install.sh`.
- Install other requirements with `cat scripts/install/tess-apt-requirements.txt | xargs sudo apt-get install -y`
- Set the tesseract data folder path
  - Find the tesseract data folder `tessdata` with `find / -name tessdata`.  Make sure to use the one corresponding to the latest tesseract version if you have multiple.
  - Create a `local.env` file in the root `marker` folder with `TESSDATA_PREFIX=/path/to/tessdata` inside it

## Mac

- Install python requirements
  - `poetry install`
  - `poetry shell` to activate your poetry venv

**Optional**

Only needed if using `ocrmypdf` as the ocr backend.

- Run `pip install ocrmypdf`
- Install system requirements from `scripts/install/tess-brew-requirements.txt`
- Set the tesseract data folder path
  - Find the tesseract data folder `tessdata` with `brew list tesseract`
  - Create a `local.env` file in the root `marker` folder with `TESSDATA_PREFIX=/path/to/tessdata` inside it

# Usage

First, some configuration.  Note that settings can be overridden with env vars, or in a `local.env` file in the root `marker` folder.

- Your torch device will be automatically detected, but you can manually set it also.  For example, `TORCH_DEVICE=cuda` or `TORCH_DEVICE=mps`. `cpu` is the default.
  - If using GPU, set `INFERENCE_RAM` to your GPU VRAM (per GPU).  For example, if you have 16 GB of VRAM, set `INFERENCE_RAM=16`.
  - Depending on your document types, marker's average memory usage per task can vary slightly.  You can configure `VRAM_PER_TASK` to adjust this if you notice tasks failing with GPU out of memory errors.
- By default, marker will use `surya` for OCR.  Surya is slower on CPU, but more accurate than tesseract.  If you want faster OCR, set `OCR_ENGINE` to `ocrmypdf`. This also requires external dependencies (see above).  If you don't want OCR at all, set `OCR_ENGINE` to `None`.
- Inspect the other settings in `marker/settings.py`.  You can override any settings in the `local.env` file, or by setting environment variables.


## Convert a single file

Run `convert_single.py`, like this:

```
python convert_single.py /path/to/file.pdf /path/to/output/folder --parallel_factor 2 --max_pages 10 --langs English
```

- `--batch_multiplier` is how much to multiply default batch sizes by if you have extra VRAM.  Higher numbers will take more VRAM, but process faster.  Set to 2 by default.  The default batch sizes will take ~3GB of VRAM.
- `--max_pages` is the maximum number of pages to process.  Omit this to convert the entire document.
- `--langs` is a comma separated list of the languages in the document, for OCR

Make sure the `DEFAULT_LANG` setting is set appropriately for your document.  The list of supported languages for OCR is [here](https://github.com/VikParuchuri/surya/blob/master/surya/languages.py).  If you need more languages, you can use any language supported by [Tesseract](https://tesseract-ocr.github.io/tessdoc/Data-Files#data-files-for-version-400-november-29-2016) if you set `OCR_ENGINE` to `ocrmypdf`.  If you don't need OCR, marker can work with any language.

## Convert multiple files

Run `convert.py`, like this:

```
python convert.py /path/to/input/folder /path/to/output/folder --workers 10 --max 10 --metadata_file /path/to/metadata.json --min_length 10000
```

- `--workers` is the number of pdfs to convert at once.  This is set to 1 by default, but you can increase it to increase throughput, at the cost of more CPU/GPU usage. Parallelism will not increase beyond `INFERENCE_RAM / VRAM_PER_TASK` if you're using GPU.
- `--max` is the maximum number of pdfs to convert.  Omit this to convert all pdfs in the folder.
- `--min_length` is the minimum number of characters that need to be extracted from a pdf before it will be considered for processing.  If you're processing a lot of pdfs, I recommend setting this to avoid OCRing pdfs that are mostly images. (slows everything down)
- `--metadata_file` is an optional path to a json file with metadata about the pdfs.  If you provide it, it will be used to set the language for each pdf.  If not, `DEFAULT_LANG` will be used. The format is:

```
{
  "pdf1.pdf": {"languages": ["English"]},
  "pdf2.pdf": {"languages": ["Spanish", "Russian"]},
  ...
}
```

You can use language names or codes.  The exact codes depend on the OCR engine.  See [here](https://github.com/VikParuchuri/surya/blob/master/surya/languages.py) for a full list for surya codes, and [here](https://tesseract-ocr.github.io/tessdoc/Data-Files#data-files-for-version-400-november-29-2016) for tesseract.

## Convert multiple files on multiple GPUs

Run `chunk_convert.sh`, like this:

```
MIN_LENGTH=10000 METADATA_FILE=../pdf_meta.json NUM_DEVICES=4 NUM_WORKERS=15 bash chunk_convert.sh ../pdf_in ../md_out
```

- `METADATA_FILE` is an optional path to a json file with metadata about the pdfs.  See above for the format.
- `NUM_DEVICES` is the number of GPUs to use.  Should be `2` or greater.
- `NUM_WORKERS` is the number of parallel processes to run on each GPU.  Per-GPU parallelism will not increase beyond `INFERENCE_RAM / VRAM_PER_TASK`.
- `MIN_LENGTH` is the minimum number of characters that need to be extracted from a pdf before it will be considered for processing.  If you're processing a lot of pdfs, I recommend setting this to avoid OCRing pdfs that are mostly images. (slows everything down)

Note that the env variables above are specific to this script, and cannot be set in `local.env`.

# Benchmarks

Benchmarking PDF extraction quality is hard.  I've created a test set by finding books and scientific papers that have a pdf version and a latex source.  I convert the latex to text, and compare the reference to the output of text extraction methods.

Benchmarks show that marker is 10x faster than nougat, and more accurate outside arXiv (nougat was trained on arXiv data).  We show naive text extraction (pulling text out of the pdf with no processing) for comparison.

**Speed**

| Method | Average Score | Time per page | Time per document |
|--------|---------------|---------------|-------------------|
| naive  | 0.350727      | 0.00152378    | 0.326524          |
| marker | 0.641062      | 0.360622      | 77.2762           |
| nougat | 0.629211      | 3.77259       | 808.413           |

**Accuracy**

First 3 are non-arXiv books, last 3 are arXiv papers.

| Method | switch_trans.pdf | crowd.pdf | multicolcnn.pdf | thinkos.pdf | thinkdsp.pdf | thinkpython.pdf |
|--------|------------------|-----------|-----------------|-------------|--------------|-----------------|
| naive  | 0.244114         | 0.140669  | 0.0868221       | 0.366856    | 0.412521     | 0.468281        |
| marker | 0.482091         | 0.466882  | 0.537062        | 0.754347    | 0.78825      | 0.779536        |
| nougat | 0.696458         | 0.552337  | 0.735099        | 0.655002    | 0.645704     | 0.650282        |

Peak GPU memory usage during the benchmark is `3.3GB` for nougat, and `3.1GB` for marker.  Benchmarks were run on an A6000.

**Throughput**

Marker takes about 3GB of VRAM on average per task, so you can convert 16 documents in parallel on an A6000.

![Benchmark results](data/images/per_doc.png)

## Running your own benchmarks

You can benchmark the performance of marker on your machine.  First, download the benchmark data [here](https://drive.google.com/file/d/1WiN4K2-jQfwyQMe4wSSurbpz3hxo2fG9/view?usp=drive_link) and unzip.

Then run `benchmark.py` like this:

```
python benchmark.py data/pdfs data/references report.json --nougat
```

This will benchmark marker against other text extraction methods.  It sets up batch sizes for nougat and marker to use a similar amount of GPU RAM for each.

Omit `--nougat` to exclude nougat from the benchmark.  I don't recommend running nougat on CPU, since it is very slow.

# Commercial usage

All models were trained from scratch, so they're okay for commercial usage.  The weights for the models are licensed cc-by-nc-sa-4.0, but I will waive that for any organization under $5M USD in gross revenue in the most recent 12-month period AND under $5M in lifetime VC/angel funding raised.

If you want to remove the GPL license requirements for inference or use the weights commercially over the revenue limit, please contact me at marker@vikas.sh for dual licensing.

Note that the `ocrmypdf` OCR option will use ocrmypdf, which includes Ghostscript, an AGPL dependency, but calls it via CLI, so it does not trigger the license provisions.  Ocrmypdf is disabled by default, and will not be installed automatically.

# Thanks

This work would not have been possible without amazing open source models and datasets, including (but not limited to):

- Surya
- Texify
- Pypdfium2/pdfium
- DocLayNet from IBM
- ByT5 from Google

Thank you to the authors of these models and datasets for making them available to the community!