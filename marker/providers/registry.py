import filetype

from marker.providers.image import ImageProvider
from marker.providers.pdf import PdfProvider


def provider_from_filepath(filepath: str):
     kind = filetype.image_match(filepath)
     if kind is not None:
        return ImageProvider

     return PdfProvider