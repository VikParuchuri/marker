from typing import Optional

from pydantic import BaseModel

from marker.util import assign_config


class BaseConverter:
    def __init__(self, config: Optional[BaseModel | dict] = None):
        assign_config(self, config)
        self.config = config

    def __call__(self, *args, **kwargs):
        raise NotImplementedError

def converter_from_mimetype(mimetype: str):
    from marker.converters.misc import LibreOfficeConverter
    from marker.converters.pdf import PdfConverter

    if any(mimetype.startswith(pdf_mimetype) for pdf_mimetype in [
        'text/pdf',
        'text/x-pdf',
        'application/pdf',
        'application/x-pdf',
        'applications/vnd.pdf',
    ]):
        return PdfConverter
    else:
        return LibreOfficeConverter
