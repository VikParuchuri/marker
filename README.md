# Marker

Marker converts PDFs to markdown, JSON, and HTML quickly and accurately.

- Supports a wide range of documents
- Supports all languages
- Removes headers/footers/other artifacts
- Formats tables and code blocks
- Extracts and saves images along with the markdown
- Converts equations to latex
- Easily extensible with your own formatting and logic
- Works on GPU, CPU, or MPS

## How it works

Marker is a pipeline of deep learning models:

- Extract text, OCR if necessary (heuristics, [surya](https://github.com/VikParuchuri/surya))
- Detect page layout and find reading order ([surya](https://github.com/VikParuchuri/surya))
- Clean and format each block (heuristics, [texify](https://github.com/VikParuchuri/texify. [tabled](https://github.com/VikParuchuri/tabled))
- Combine blocks and postprocess complete text

It only uses models where necessary, which improves speed and accuracy.

## Examples

| PDF                                                                   | Markdown        | JSON                                                                                                 |
| [Think Python](https://greenteapress.com/thinkpython/thinkpython.pdf) | Textbook    | [View](https://github.com/VikParuchuri/marker/blob/master/data/examples/marker/thinkpython.md)     |
| [Think OS](https://greenteapress.com/thinkos/thinkos.pdf)             | Textbook    | [View](https://github.com/VikParuchuri/marker/blob/master/data/examples/marker/thinkos.md)             |
| [Switch Transformers](https://arxiv.org/pdf/2101.03961.pdf)           | arXiv paper |  [View](https://github.com/VikParuchuri/marker/blob/master/data/examples/nougat/switch_transformers.md) |
| [Multi-column CNN](https://arxiv.org/pdf/1804.07821.pdf)              | arXiv paper | [View](https://github.com/VikParuchuri/marker/blob/master/data/examples/nougat/multicolcnn.md)        |

## Performance

![Benchmark overall](data/images/overall.png)

The above results are with marker setup so it takes ~4GB of VRAM on an A6000.

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

- Marker will not convert inline equations
- Tables are not always formatted 100% correctly - multiline cells are sometimes split into multiple rows.
- Forms are not converted optimally
- Very complex layouts, with nested tables and forms, may not work

# Installation

You'll need python 3.9+ and PyTorch.  You may need to install the CPU version of torch first if you're not using a Mac or a GPU machine.  See [here](https://pytorch.org/get-started/locally/) for more details.

Install with:

```shell
pip install marker-pdf
```

# Usage

First, some configuration:

- Your torch device will be automatically detected, but you can override this.  For example, `TORCH_DEVICE=cuda`.
- Some PDFs, even digital ones, have bad text in them.  Set the `force_ocr` flag on the CLI or via configuration to ensure your PDF runs through OCR.

## Interactive App

I've included a streamlit app that lets you interactively try marker with some basic options.  Run it with:

```shell
pip install streamlit
marker_gui
```

## Convert a single file

```shell
marker_single /path/to/file.pdf
```

Options:
- `--output_dir PATH`: Directory where output files will be saved. Defaults to the value specified in settings.OUTPUT_DIR.
- `--debug`: Enable debug mode for additional logging and diagnostic information.
- `--output_format [markdown|json|html]`: Specify the format for the output results.
- `--page_range TEXT`: Specify which pages to process. Accepts comma-separated page numbers and ranges. Example: `--page_range "0,5-10,20"` will process pages 0, 5 through 10, and page 20.
- `--force_ocr`: Force OCR processing on the entire document, even for pages that might contain extractable text.
- `--processors TEXT`: Override the default processors by providing their full module paths, separated by commas. Example: `--processors "module1.processor1,module2.processor2"`
- `--config_json PATH`: Path to a JSON configuration file containing additional settings.
- `--languages TEXT`: Optionally specify which languages to use for OCR processing. Accepts a comma-separated list. Example: `--languages "eng,fra,deu"` for English, French, and German.
- `-l`: List all available builders, processors, and converters, and their associated configuration.  These values can be used to build a JSON configuration file for additional tweaking of marker defaults.

The list of supported languages for surya OCR is [here](https://github.com/VikParuchuri/surya/blob/master/surya/languages.py).  If you don't need OCR, marker can work with any language.

## Convert multiple files

```shell
marker /path/to/input/folder --workers 10
```

- `marker` supports all the same options from `marker_single` above.
- `--workers` is the number of conversion workers to run simultaneously.  This is set to 1 by default, but you can increase it to increase throughput, at the cost of more CPU/GPU usage.  Marker will use 5GB of VRAM per worker at the peak, and 3.5GB average.

## Convert multiple files on multiple GPUs

```shell
NUM_DEVICES=4 NUM_WORKERS=15 marker_chunk_convert ../pdf_in ../md_out
```

- `NUM_DEVICES` is the number of GPUs to use.  Should be `2` or greater.
- `NUM_WORKERS` is the number of parallel processes to run on each GPU.
- 

## Use from python

See the `PdfConverter` class at `marker/converters/pdf.py` function for additional arguments that can be passed.

```python
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

converter = PdfConverter(
    artifact_dict=create_model_dict(),
)
rendered = converter("FILEPATH")
text, _, images = text_from_rendered(rendered)
```

`rendered` will be a pydantic basemodel with different properties depending on the output type requested.  With markdown output (default), you'll have the properties `markdown`, `metadata`, and `images`.  For json output, you'll have `children`, `block_type`, and `metadata`.

### Custom configuration

You can also pass configuration using the `ConfigParser`:

```python
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser

config = {
    "output_format": "json",
    "ADDITIONAL_KEY": "VALUE"
}
config_parser = ConfigParser(config)

converter = PdfConverter(
    config=config_parser.generate_config_dict(),
    artifact_dict=create_model_dict(),
    processor_list=config_parser.get_processors(),
    renderer=config_parser.get_renderer()
)
rendered = converter("FILEPATH")
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

Note that this is not a very robust API, and is only intended for small-scale use.  If you want to use this server, but want a more robust conversion option, you can use the hosted [Datalab API](https://www.datalab.to/plans).

# Troubleshooting

There are some settings that you may find useful if things aren't working the way you expect:

- Make sure to set `force_ocr` if you see garbled text - this will re-OCR the document.
- `TORCH_DEVICE` - set this to force marker to use a given torch device for inference.
- If you're getting out of memory errors, decrease worker count.  You can also try splitting up long PDFs into multiple files.

## Debugging

Pass the `debug` option to activate debug mode.  This will save images of each page with detected layout and text, as well as output a json file with additional bounding box information.

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