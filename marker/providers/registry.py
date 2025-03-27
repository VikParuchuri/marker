import filetype
import filetype.match as file_match
from bs4 import BeautifulSoup
from filetype.types import archive, document, IMAGE

from marker.providers.document import DocumentProvider
from marker.providers.epub import EpubProvider
from marker.providers.html import HTMLProvider
from marker.providers.image import ImageProvider
from marker.providers.pdf import PdfProvider
from marker.providers.powerpoint import PowerPointProvider
from marker.providers.spreadsheet import SpreadSheetProvider

DOCTYPE_MATCHERS = {
    "image": IMAGE,
    "pdf": [
        archive.Pdf,
    ],
    "epub": [
        archive.Epub,
    ],
    "doc": [document.Docx],
    "xls": [document.Xlsx],
    "ppt": [document.Pptx],
}


def load_matchers(doctype: str):
    return [cls() for cls in DOCTYPE_MATCHERS[doctype]]


def load_extensions(doctype: str):
    return [cls.EXTENSION for cls in DOCTYPE_MATCHERS[doctype]]


def provider_from_ext(filepath: str):
    ext = filepath.rsplit(".", 1)[-1].strip()
    if not ext:
        return PdfProvider

    if ext in load_extensions("image"):
        return ImageProvider
    if ext in load_extensions("pdf"):
        return PdfProvider
    if ext in load_extensions("doc"):
        return DocumentProvider
    if ext in load_extensions("xls"):
        return SpreadSheetProvider
    if ext in load_extensions("ppt"):
        return PowerPointProvider
    if ext in load_extensions("epub"):
        return EpubProvider
    if ext in ["html"]:
        return HTMLProvider

    return PdfProvider


def provider_from_filepath(filepath: str):
    if filetype.image_match(filepath) is not None:
        return ImageProvider
    if file_match(filepath, load_matchers("pdf")) is not None:
        return PdfProvider
    if file_match(filepath, load_matchers("epub")) is not None:
        return EpubProvider
    if file_match(filepath, load_matchers("doc")) is not None:
        return DocumentProvider
    if file_match(filepath, load_matchers("xls")) is not None:
        return SpreadSheetProvider
    if file_match(filepath, load_matchers("ppt")) is not None:
        return PowerPointProvider

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
            # Check if there are any HTML tags
            if bool(soup.find()):
                return HTMLProvider
    except Exception:
        pass

    # Fallback if we incorrectly detect the file type
    return provider_from_ext(filepath)
