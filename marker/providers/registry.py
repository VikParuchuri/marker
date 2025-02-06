import filetype
import filetype.match as match
from bs4 import BeautifulSoup
from filetype.types import archive, document

from marker.providers.document import DocumentProvider
from marker.providers.epub import EpubProvider
from marker.providers.html import HTMLProvider
from marker.providers.image import ImageProvider
from marker.providers.pdf import PdfProvider
from marker.providers.powerpoint import PowerPointProvider
from marker.providers.spreadsheet import SpreadSheetProvider


def provider_from_filepath(filepath: str):
    if filetype.image_match(filepath) is not None:
        return ImageProvider
    if match(filepath, (archive.Pdf(),)) is not None:
        return PdfProvider
    if match(filepath, (archive.Epub(),)) is not None:
        return EpubProvider
    if match(
            filepath, (
                document.Doc(),
                document.Docx(),
                document.Odt()
            )) is not None:
        return DocumentProvider
    if match(
            filepath, (
                document.Xls(),
                document.Xlsx(),
                document.Ods(),
            )) is not None:
        return SpreadSheetProvider
    if match(
            filepath, (
                document.Ppt(),
                document.Pptx(),
                document.Odp(),
            )) is not None:
        return PowerPointProvider

    try:
        soup = BeautifulSoup(open(filepath, 'r').read(), 'html.parser')
        # Check if there are any HTML tags
        if bool(soup.find()):
            return HTMLProvider
    except:
        pass

    return PdfProvider
