from marker.converters.pdf import PdfConverter
from marker.providers.misc import LibreOfficeProvider
from typing import Any, Dict, List

class LibreOfficeConverter(PdfConverter):
    def __init__(self, artifact_dict: Dict[str, Any], processor_list: List[str] | None = None, renderer: str | None = None, config=None):
        super().__init__(artifact_dict, processor_list, renderer, config)
        self.provider_class = LibreOfficeProvider
