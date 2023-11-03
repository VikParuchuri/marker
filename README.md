# Marker

This project converts PDF, EPUB, and MOBI to Markdown, balancing speed with quality.  It can run on GPU or CPU, and 

- Equations will be detected and converted to Latex when possible
- Headers/footers/other artifacts will be removed
- Tables will be formatted properly
- Code blocks will be formatted properly

PDF is a tricky format, so this will not always work perfectly, but it is good enough for most purposes.


## Install

- Recommend installing tesseract 5 by following [these instructions](https://notesalexp.org/tesseract-ocr/html/).  You may get tesseract 4 otherwise.
- Install ghostscript > 9.55
- Install apt requirements
- Set `TESSDATA_PREFIX`
  - Find tessdata folder
- `poetry install`


## Usage

Can work with CPU, MPS, or GPU