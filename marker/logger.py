import logging
import fitz as pymupdf
import warnings


def configure_logging():
    logging.basicConfig(level=logging.WARNING)

    logging.getLogger('pdfminer').setLevel(logging.ERROR)
    logging.getLogger('PIL').setLevel(logging.ERROR)
    logging.getLogger('fitz').setLevel(logging.ERROR)
    logging.getLogger('ocrmypdf').setLevel(logging.ERROR)
    pymupdf.TOOLS.mupdf_display_errors(False)
    warnings.simplefilter(action='ignore', category=FutureWarning)