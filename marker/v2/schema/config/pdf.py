from typing import Optional

from marker.v2.schema.config.provider import ProviderConfig


class PdfProviderConfig(ProviderConfig):
    pdftext_workers: int = 4
    flatten_pdf: bool = True
