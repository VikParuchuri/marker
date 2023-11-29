# Marker

Marker converts PDF, EPUB, and MOBI to Markdown.  It is 10x faster than nougat, works across many types of documents, and minimizes the risk of hallucinations significantly.

Features:

- Support for a range of PDF documents (optimized for books and scientific papers)
- Support for 1 and 2 column layouts
- Removal of headers/footers/other artifacts
- Latex conversion for most equations
- Proper code block and table formatting
- Support for multiple languages (although most testing is done in English).  See `settings.py` for a list of supported languages.
- Works on GPU, CPU, or MPS

## How it works

Marker is a pipeline of steps and deep learning models:

- Loop through each document page, and:
  - OCR the page if text cannot be detected
  - Detect page layout
  - Format blocks properly based on layout
- Combine text from all pages
- Postprocess extracted text

Marker minimizes the use of autoregressive models, which reduces the risk of hallucinations to close to zero, and improves speed.  The only parts of a document that are passed through an LLM forward pass are equation blocks.

## Limitations

PDF is a tricky format, so marker will not always work perfectly.  Here are some known limitations that are on the roadmap to address:

- Marker will convert fewer equations to latex that nougat.  This is because it has to first detect equations, then convert them without hallucation.
- Marker is much faster than autoregressive methods like nougat or kosmos, but much slower than just extracting text directly from the pdf with no processing.
- Whitespace and indentations are not always respected.
- Images and most charts will be removed, since text can't be extracted effectively.
- Only languages similar to English (Spanish, French, German, Russian, etc) are supported.  Languages with different character sets (Chinese, Japanese, Korean, etc) are not.

# Installation

This has been tested on Mac and Linux (Ubuntu and Debian).  You will need python 3.9+ and [poetry](https://python-poetry.org/docs/#installing-with-the-official-installer).

First, clone the repo:

- `git clone https://github.com/VikParuchuri/marker.git`
- `cd marker`

## Linux

- Install system requirements
  - `cat install/apt-requirements.txt | xargs sudo apt-get install -y`
  - Optional: Install tesseract 5 by following [these instructions](https://notesalexp.org/tesseract-ocr/html/) or running `install/tesseract_5_install.sh`.
  - Install ghostscript > 9.55 by following [these instructions](https://ghostscript.readthedocs.io/en/latest/Install.html) or running `install/ghostscript_install.sh`.
- Set the tesseract data folder path
  - Find the tesseract data folder `tessdata` with `find / -name tessdata`.  Make sure to use the one corresponding to the right tesseract version if you have multiple!
  - Create a `local.env` file in the root `marker` folder with `TESSDATA_PREFIX=/path/to/tessdata` inside it
- Install python requirements
  - `poetry install`
  - `poetry shell` to activate your poetry venv
  - GPU only: run `pip install torch` to install other torch dependencies.

## Mac

- Install system requirements from `install/brew-requirements.txt`
- Set the tesseract data folder path
  - Find the tesseract data folder `tessdata` with `brew list tesseract`
  - Create a `local.env` file in the root `marker` folder with `TESSDATA_PREFIX=/path/to/tessdata` inside it
- Install python requirements
  - `poetry install`
  - `poetry shell` to activate your poetry venv

# Usage

**Configuration**

- Set your torch device in the `local.env` file.  For example, `TORCH_DEVICE=cuda` or `TORCH_DEVICE=mps`.  `cpu` is the default.
  - If using GPU, set `INFERENCE_RAM` to your GPU VRAM (per GPU).  For example, if you have 16 GB of VRAM, set `INFERENCE_RAM=16`.
  - Depending on your document types, marker's average memory usage per task can vary slightly.  You can configure `VRAM_PER_TASK` to adjust this if you notice tasks failing with GPU out of memory errors.
- Inspect the settings in `marker/settings.py`.  You can override any settings in the `local.env` file, or by setting environment variables.

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
python convert.py /path/to/input/folder /path/to/output/folder --workers 4 --max 10 --metadata_file /path/to/metadata.json
```

- `--workers` is the number of pdfs to convert at once.  This is set to 1 by default, but you can increase it to increase throughput, at the cost of more CPU/GPU usage. Parallelism will not increase beyond `INFERENCE_RAM / VRAM_PER_TASK` if you're using GPU.
- `--max` is the maximum number of pdfs to convert.  Omit this to convert all pdfs in the folder.
- `--metadata_file` is an optional path to a json file with metadata about the pdfs.  If you provide it, it will be used to set the language for each pdf.  If not, `DEFAULT_LANG` will be used. The format is:

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
METADATA_FILE=../pdf_meta.json NUM_DEVICES=4 NUM_WORKERS=35 bash chunk_convert.sh ../pdf_in ../md_out
```

- `METADATA_FILE` is an optional path to a json file with metadata about the pdfs.  See above for the format.
- `NUM_DEVICES` is the number of GPUs to use.  Should be `2` or greater.
- `NUM_WORKERS` is the number of parallel processes to run on each GPU.  Per-GPU parallelism will not increase beyond `INFERENCE_RAM / VRAM_PER_TASK`.

# Benchmarks

Benchmarking PDF extraction quality is hard.  I've created a test set by finding books and scientific papers that have a pdf version and a latex source.  I converted the latex to text, and compared the reference to the output of text extraction methods.

Benchmarks show that marker is 10x faster than nougat, and more accurate outside arXiv (nougat was trained on arXiv data).

**Speed**

The books are several hundred pages long (paip is almost 1000 pages).

Method      Average Score    Time per doc
--------  ---------------  --------------
naive            0.351585        0.328931
marker           0.636839       78.1468
nougat           0.614548      810.756

**Accuracy**

First 4 are non-arXiv books, last 3 are arXiv papers.

Method      thinkos.pdf    thinkdsp.pdf    thinkpython.pdf    paip.pdf    switch_trans.pdf    crowd.pdf    multicolcnn.pdf
--------  -------------  --------------  -----------------  ----------  ------------------  -----------  -----------------
naive          0.366817        0.412014           0.468147    0.735464             0.244739     0.14489           0.0890217
marker         0.753291        0.787938           0.779262    0.679189             0.478387     0.446068          0.533737
nougat         0.638434        0.632723           0.637626    0.462495             0.690028     0.540994          0.699539

Peak GPU memory usage during the benchmark is `3.3GB` for nougat, and `2.7GB` for marker.  Benchmarks were run on an A6000.

## Running your own benchmarks

You can benchmark the performance of marker on your machine.

Run `benchmark.py` like this:

```
python benchmark.py benchmark_data/pdfs benchmark_data/references report.json --nougat
```

This will benchmark marker against other text extraction methods.  It sets up batch sizes for nougat and marker to use a similar amount of GPU RAM for each.

Omit `--nougat` to exclude nougat from the benchmark.  I don't recommend running nougat on CPU, since it is very slow.

# Commercial usage

Due to the licensing of the underlying models like layoutlmv3 and nougat, this is only suitable for noncommercial usage.  I'm building a version that can be used commercially. If you would like to get early access, email me at marker@vikas.sh.

# Thanks

This work would not have been possible without amazing open source models and datasets, including (but not limited to):

- Nougat from Meta
- Layoutlmv3 from Microsoft
- DocLayNet from IBM
- ByT5 from Google