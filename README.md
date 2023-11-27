# Marker

Marker converts PDF, EPUB, and MOBI to Markdown.  It is up to 10x faster than nougat, works across many types of documents, and minimizes the risk of hallucinations significantly.

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

This has been tested on Mac and Linux (Ubuntu).

**Clone repo**

- `git clone https://github.com/VikParuchuri/marker.git`
- `cd marker`

**System packages**

- Install the system requirements at `install/apt-requirements.txt` for Linux or `install/brew-requirements.txt` for Mac
  - Linux only: Install tesseract 5 by following [these instructions](https://notesalexp.org/tesseract-ocr/html/).  You may get tesseract 4 otherwise.
  - Linux only: Install ghostscript > 9.55 (see `install/ghostscript_install.sh` for the commands).
- Set the tesseract data folder path
  - Find the tesseract data folder `tessdata`
    - On mac, you can run `brew list tesseract`
    - On linux, run `find / -name tessdata`
  - Create a `local.env` file in the root `marker` folder with `TESSDATA_PREFIX=/path/to/tessdata` inside it

**Python packages**

- `poetry install`

# Usage

**Configuration**

- Set your torch device in the `local.env` file.  For example, `TORCH_DEVICE=cuda` or `TORCH_DEVICE=mps`.  `cpu` is the default.
  - If using GPU, set `INFERENCE_RAM` to your GPU VRAM (per GPU).  For example, if you have 16 GB of VRAM, set `INFERENCE_RAM=16`.
  - Depending on your document types, marker's average memory usage per task can vary.  You can configure `VRAM_PER_TASK` to adjust this if you notice tasks failing with GPU out of memory errors.
- Inspect the settings in `marker/settings.py`.  You can override any settings in the `local.env` file, or by setting environment variables.

## Convert a single file

Run `convert_single.py`, like this:

```
python convert_single.py /path/to/file.pdf /path/to/output.md --workers 4 --max_pages 10
```

- `--workers` is the number of parallel CPU processes to run for OCR.  This is set to 1 by default, but you can increase it to speed up processing.
- `--max_pages` is the maximum number of pages to process.  Omit this to convert the entire document.

Make sure the `DEFAULT_LANG` setting is set correctly for this.

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

Benchmarking PDF extraction quality is hard.  I've created a test set by finding books and scientific papers that have a pdf version and a latex source.  I can then convert the latex to text, and compare it to the output of marker using edit distance.

Benchmarks show that marker is up to 10x faster than nougat, and more accurate outside arXiv (nougat is better inside arXiv):




Peak GPU memory usage during the benchmark is `3.3GB` for nougat, and `3.7GB` for marker.

## Running your own benchmarks

You can benchmark the performance of marker on your machine.  The benchmark consists of 3 scientific papers from arXiv, and 3 textbooks. 

Run `benchmark.py` like this:

```
python benchmark.py benchmark_data/pdfs benchmark_data/references report.json --nougat
```

This will benchmark marker against other text extraction methods.  It sets up batch sizes for nougat and marker to use a similar amount of GPU RAM for each (4GB).

Omit `--nougat` to exclude nougat from the benchmark.  I don't recommend running nougat on CPU, since it is very slow.

# Commercial usage

Due to the licensing of the underlying models like layoutlmv3 and nougat, this is only suitable for noncommercial usage.  I'm building a version that can be used commercially. If you would like to get early access, email me at marker@vikas.sh.

# Thanks

This work would not have been possible without amazing open source models and datasets, including:

- Nougat from Meta
- Layoutlmv3 from Microsoft
- DocLayNet from IBM
- BLOOM from BigScience