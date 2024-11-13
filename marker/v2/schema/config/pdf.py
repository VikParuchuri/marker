from typing import Optional, Tuple

from marker.v2.schema.config.provider import ProviderConfig


class PdfProviderConfig(ProviderConfig):
    page_range: Optional[Tuple[int, int]] = None
    pdftext_workers: int = 4
    flatten_pdf: bool = True
