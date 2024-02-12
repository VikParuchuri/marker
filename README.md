# Marker

Marker converts PDF, EPUB, and MOBI to markdown.  It's 10x faster than nougat, more accurate on most documents, and has low hallucination risk.

- Support for a range of PDF documents (optimized for books and scientific papers)
- Removes headers/footers/other artifacts
- Converts most equations to latex
- Formats code blocks and tables
- Support for multiple languages (although most testing is done in English).  See `settings.py` for a language list, or to add your own.
- Works on GPU, CPU, or MPS

## How it works

Marker is a pipeline of deep learning models:

- Extract text, OCR if necessary (heuristics, tesseract)
- Detect page layout ([layout segmenter](https://huggingface.co/vikp/layout_segmenter), [column detector](https://huggingface.co/vikp/column_detector))
- Clean and format each block (heuristics, [texify](https://huggingface.co/vikp/texify))
- Combine blocks and postprocess complete text (heuristics, [pdf_postprocessor](https://huggingface.co/vikp/pdf_postprocessor_t5))

Relying on autoregressive forward passes to generate text is slow and prone to hallucination/repetition.  From the nougat paper: `We observed [repetition] in 1.5% of pages in the test set, but the frequency increases for out-of-domain documents.`  In my anecdotal testing, repetitions happen on 5%+ of out-of-domain (non-arXiv) pages.  

Nougat is an amazing model, but I wanted a faster and more general purpose solution. Marker is 10x faster and has low hallucination risk because it only passes equation blocks through an LLM forward pass.

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

- Marker will not convert 100% of equations to LaTeX.  This is because it has to first detect equations, then convert them.
- Whitespace and indentations are not always respected.
- Not all lines/spans will be joined properly.
- Languages similar to English (Spanish, French, German, Russian, etc) have the best support. There is provisional support for Chinese, Japanese, Korean, and Hindi, but it may not work as well.  You can add other languages by adding them to the `TESSERACT_LANGUAGES` and `SPELLCHECK_LANGUAGES` settings in `settings.py`.
- This works best on digital PDFs that won't require a lot of OCR.  It's optimized for speed, and limited OCR is used to fix errors.

# Installation

This has been tested on Mac, Linux (Ubuntu and Debian) and Windows 11.  You'll need python 3.9+ and [poetry](https://python-poetry.org/docs/#installing-with-the-official-installer).

First, clone the repo:

- `git clone https://github.com/VikParuchuri/marker.git`
- `cd marker`

## Linux

- Install system requirements
  - Optional: Install tesseract 5 by following [these instructions](https://notesalexp.org/tesseract-ocr/html/) or running `scripts/install/tesseract_5_install.sh`.
  - Install ghostscript > 9.55 by following [these instructions](https://ghostscript.readthedocs.io/en/latest/Install.html) or running `scripts/install/ghostscript_install.sh`.
  - Install other requirements with `cat scripts/install/apt-requirements.txt | xargs sudo apt-get install -y`
- Set the tesseract data folder path
  - Find the tesseract data folder `tessdata` with `find / -name tessdata`.  Make sure to use the one corresponding to the latest tesseract version if you have multiple.
  - Create a `local.env` file in the root `marker` folder with `TESSDATA_PREFIX=/path/to/tessdata` inside it
- Install python requirements
  - `poetry install`
  - `poetry shell` to activate your poetry venv
- Update pytorch since poetry doesn't play nicely with it
  - GPU only: run `pip install torch` to install other torch dependencies.
  - CPU only: Uninstall torch with `poetry remove torch`, then follow the [CPU install](https://pytorch.org/get-started/locally/) instructions.

## Mac

- Install system requirements from `scripts/install/brew-requirements.txt`
- Set the tesseract data folder path
  - Find the tesseract data folder `tessdata` with `brew list tesseract`
  - Create a `local.env` file in the root `marker` folder with `TESSDATA_PREFIX=/path/to/tessdata` inside it
- Install python requirements
  - `poetry install`
  - `poetry shell` to activate your poetry venv

## Windows
- Optional: Install `tesseract` by following [these instructions](https://github.com/UB-Mannheim/tesseract/wiki) or running `winget install -e --id UB-Mannheim.TesseractOCR`.
- Install `ghostscript` > 9.55 by downloading it [here](https://ghostscript.com/releases/gsdnld.html).
- Install `poetry` by following [these instructions](https://python-poetry.org/docs/#installing-with-pipx) or by running `pipx install poetry` (if you don't already have `pipx` installed, you may follow [these instructions](https://github.com/pypa/pipx) or run `pip install pipx` followed by `pipx ensurepath`).
- Install `poetry` dependencies by running `poetry update`.
- Enter your new `poetry` environment by running `poetry shell`.
- Install `libmagic` by running `pip install python-magic-bin==0.4.14`.
- If you wish to use a GPU, uninstall `torch` by running `pip uninstall torch` and then reinstall `torch` for your version of CUDA as described [here](https://pytorch.org/get-started/locally/).
- Install `setuptools` by running `pip install setuptools`.
- Create a file in the root `marker` directory named `local.env` which contains environment variables on each line in the following format: `FOO_ENV_VAR=BAR_VALUE` (for example, to set the default language to English, add the following line: `DEFAULT_LANG=English`).

# Usage

First, some configuration.  Note that settings can be overridden with env vars, or in a `local.env` file in the root `marker` folder.

- Your torch device will be automatically detected, but you can manually set it also.  For example, `TORCH_DEVICE=cuda` or `TORCH_DEVICE=mps`. `cpu` is the default.
  - If using GPU, set `INFERENCE_RAM` to your GPU VRAM (per GPU).  For example, if you have 16 GB of VRAM, set `INFERENCE_RAM=16`.
  - Depending on your document types, marker's average memory usage per task can vary slightly.  You can configure `VRAM_PER_TASK` to adjust this if you notice tasks failing with GPU out of memory errors.
- Inspect the other settings in `marker/settings.py`.  You can override any settings in the `local.env` file, or by setting environment variables.
  - By default, the final editor model is off.  Turn it on with `ENABLE_EDITOR_MODEL=true`.
  - By default, marker will use ocrmypdf for OCR, which is slower than base tesseract, but higher quality.  You can change this with the `OCR_ENGINE` setting.

## Convert a single file

Run `convert_single.py`, like this:

```
python convert_single.py /path/to/file.pdf /path/to/output.md --parallel_factor 2 --max_pages 10
```

- `--parallel_factor` is how much to increase batch size and parallel OCR workers by.  Higher numbers will take more VRAM and CPU, but process faster.  Set to 1 by default.
- `--max_pages` is the maximum number of pages to process.  Omit this to convert the entire document.

Make sure the `DEFAULT_LANG` setting is set appropriately for your document.

## Convert multiple files

Run `convert.py`, like this:

```
python convert.py /path/to/input/folder /path/to/output/folder --workers 10 --max 10 --metadata_file /path/to/metadata.json --min_length 10000
```

- `--workers` is the number of pdfs to convert at once.  This is set to 1 by default, but you can increase it to increase throughput, at the cost of more CPU/GPU usage. Parallelism will not increase beyond `INFERENCE_RAM / VRAM_PER_TASK` if you're using GPU.
- `--max` is the maximum number of pdfs to convert.  Omit this to convert all pdfs in the folder.
- `--metadata_file` is an optional path to a json file with metadata about the pdfs.  If you provide it, it will be used to set the language for each pdf.  If not, `DEFAULT_LANG` will be used. The format is:
- `--min_length` is the minimum number of characters that need to be extracted from a pdf before it will be considered for processing.  If you're processing a lot of pdfs, I recommend setting this to avoid OCRing pdfs that are mostly images. (slows everything down)

```
{
  "pdf1.pdf": {"language": "English"},
  "pdf2.pdf": {"language": "Spanish"},
  ...
}
```

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

Marker takes about 2GB of VRAM on average per task, so you can convert 24 documents in parallel on an A6000.

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

Due to the licensing of the underlying models like layoutlmv3 and nougat, this is only suitable for noncommercial usage.  

I'm building a version that can be used commercially, by stripping out the dependencies below. If you would like to get early access, email me at marker@vikas.sh.

Here are the non-commercial/restrictive dependencies:

- LayoutLMv3: CC BY-NC-SA 4.0 .  [Source](https://huggingface.co/microsoft/layoutlmv3-base)
- PyMuPDF - GPL . [Source](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)

Other dependencies/datasets are openly licensed (doclaynet, byt5), or used in a way that is compatible with commercial usage (ghostscript).

# Thanks

This work would not have been possible without amazing open source models and datasets, including (but not limited to):

- Nougat from Meta
- Layoutlmv3 from Microsoft
- DocLayNet from IBM
- ByT5 from Google

Thank you to the authors of these models and datasets for making them available to the community!
