# Marker

This project converts PDF, EPUB, and MOBI to Markdown, balancing speed with quality.  It runs on GPU or CPU, with configurable parallelism.  It is up to 10x faster than nougat, and minimizes hallucinations.

Features:

- Latex conversion for most equations
- Removal of headers/footers/other artifacts
- Proper code block and table formatting
- Support for multiple languages (although most testing is done in English)
- Support for a range of PDF documents (optimized for books and scientific papers)
- Works on GPU, CPU, or MPS (mac)

PDF is a tricky format, so this will not always work perfectly, but it is good enough for most purposes.

## How it works

Marker is a pipeline of steps and deep learning models:

- OCR if text cannot be detected
- Detect page layout
- Format blocks properly based on layout
- Postprocess extracted text

Marker minimizes autoregression, which reduces the risk of hallucinations to close to zero, and improves speed.  The only parts of the document that are passed through an LLM forward pass are equation regions.

## Limitations

- Marker will convert fewer equations to latex that nougat.  This is because it has to first detect equations, then convert them without hallucation.
- Marker is much faster than autoregressive methods, but much slower than heuristic methods like pdftotext.
- Whitespace and indentations are not always respected.
- Multicolumn documents will not always be in the correct order

# Installation

This has been tested on Mac, and Ubuntu.

**Clone repo**

- `git clone https://github.com/VikParuchuri/marker.git`
- `cd marker`

**System packages**

- Install the system requirements at `install/apt-requirements.txt` for Linux or `install/brew-requirements.txt` for Mac
  - Linux only: Install tesseract 5 by following [these instructions](https://notesalexp.org/tesseract-ocr/html/).  You may get tesseract 4 otherwise.
  - Linux only: Install ghostscript > 9.55 (see `install/ghostscript_install.sh` for details).
- Set the tesseract data folder path
  - Find the tesseract data folder `tessdata`
    - On mac, you can run `brew list tesseract`
    - Or run `find / -name tessdata` to find it
  - Create a `local.env` file with `TESSDATA_PREFIX=/path/to/tessdata` inside it

**Python packages**

- `poetry install`

# Usage

**Configuration**

- Set your torch device in the `local.env` file.  For example, `TORCH_DEVICE=cuda` or `TORCH_DEVICE=mps`.  `cpu` is the default.
  - If using GPU, set `MAX_TASKS_PER_GPU` to your GPU VRAM (per GPU) divided by 1.5 GB.  For example, if you have 16 GB of VRAM, set `MAX_TASKS_PER_GPU=10`.
- Inspect the settings in `marker/settings.py`.  You can override any settings in the `local.env` file, or by setting environment variables.

## Convert a single file

Run `convert_single.py`, like this:

```
python convert_single.py /path/to/file.pdf /path/to/output.md --workers 4 --max_pages 10
```

- `--workers` is the number of parallel processes to run.  This is set to 1 by default, but you can increase it to speed up processing, at the cost of more CPU/GPU usage.
- `--max_pages` is the maximum number of pages to process.  Omit this to convert the entire document.

Make sure the `DEFAULT_LANG` setting is set correctly for this.

## Convert multiple files

Run `convert.py`, like this:

```
python convert.py /path/to/input/folder /path/to/output/folder --workers 4 --max 10 --metadata_file /path/to/metadata.json
```

- `--workers` is the number of pdfs to convert at once.  This is set to 1 by default, but you can increase it to speed up processing, at the cost of more CPU/GPU usage. This should not be higher than the `MAX_TASKS_PER_GPU` setting.
- `--max` is the maximum number of pdfs to convert.  Omit this to convert all pdfs in the folder.
- `--metadata_file` is an optional path to a json file with metadata about the pdfs.  If you provide it, it will be used to set the language for each pdf.  If not, `DEFAULT_LANG` will be used. The format is:

```
{
  "pdf1.pdf": {"language": "English"},
  "pdf2.pdf": {"language": "English"},
  ...
}
```

## Convert multiple files on multiple GPUs

Run `chunk_convert.sh`, like this:

```
METADATA_FILE=../pdf_meta.json NUM_DEVICES=4 NUM_WORKERS=35 bash chunk_convert.sh ../pdf_in ../md_out
```

- `METADATA_FILE` is an optional path to a json file with metadata about the pdfs.  See above for the format.
- `NUM_DEVICES` is the number of GPUs to use.  Should be 2 or greater.
- `NUM_WORKERS` is the number of parallel processes to run on each GPU.  This should not be higher than the `MAX_TASKS_PER_GPU` setting.

## Benchmark

You can also benchmark the performance of the pipeline on your machine.  Run `benchmark.py`, like this:

```
python benchmark.py benchmark_data/pdfs benchmark_data/references report.json --nougat
```

This will benchmark marker against other text extraction methods.  Omit `--nougat` to exclude nougat from the benchmark. (it will take longer)
