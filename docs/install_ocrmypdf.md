## Linux

- Run `apt-get install ocrmypdf`
- Install ghostscript > 9.55 by following [these instructions](https://ghostscript.readthedocs.io/en/latest/Install.html) or running `scripts/install/ghostscript_install.sh`.
- Run `pip install ocrmypdf`
- Install any tesseract language packages that you want (example `apt-get install tesseract-ocr-eng`)
- Set the tesseract data folder path
  - Find the tesseract data folder `tessdata` with `find / -name tessdata`.  Make sure to use the one corresponding to the latest tesseract version if you have multiple.
  - Create a `local.env` file in the root `marker` folder with `TESSDATA_PREFIX=/path/to/tessdata` inside it

## Mac

Only needed if using `ocrmypdf` as the ocr backend.

- Run `brew install ocrmypdf`
- Run `brew install tesseract-lang` to add language support
- Run `pip install ocrmypdf`
- Set the tesseract data folder path
  - Find the tesseract data folder `tessdata` with `brew list tesseract`
  - Create a `local.env` file in the root `marker` folder with `TESSDATA_PREFIX=/path/to/tessdata` inside it

## Windows

- Install `ocrmypdf` and ghostscript by following [these instructions](https://ocrmypdf.readthedocs.io/en/latest/installation.html#installing-on-windows)
- Run `pip install ocrmypdf`
- Install any tesseract language packages you want
- Set the tesseract data folder path
  - Find the tesseract data folder `tessdata` with `brew list tesseract`
  - Create a `local.env` file in the root `marker` folder with `TESSDATA_PREFIX=/path/to/tessdata` inside it