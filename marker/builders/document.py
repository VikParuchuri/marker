from marker.settings import settings
from marker.builders import BaseBuilder
from marker.builders.layout import LayoutBuilder
from marker.builders.ocr import OcrBuilder
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.registry import get_block_class


class DocumentBuilder(BaseBuilder):
    """
    Constructs a Document given a PdfProvider, LayoutBuilder, and OcrBuilder.

    Attributes:
        lowres_image_dpi (int): 
            DPI setting for low-resolution page images used for Layout and Line Detection.
            Default is 96.

        highres_image_dpi (int): 
            DPI setting for high-resolution page images used for OCR.
            Default is 192.
    """
    lowres_image_dpi: int = 96
    highres_image_dpi: int = 192

    def __call__(self, provider: PdfProvider, layout_builder: LayoutBuilder, ocr_builder: OcrBuilder):
        document = self.build_document(provider)
        layout_builder(document, provider)
        ocr_builder(document, provider)
        return document

    def build_document(self, provider: PdfProvider):
        PageGroupClass: PageGroup = get_block_class(BlockTypes.Page)
        initial_pages = [
            PageGroupClass(
                page_id=i,
                lowres_image=provider.get_image(i, self.lowres_image_dpi),
                highres_image=provider.get_image(i, self.highres_image_dpi),
                polygon=provider.get_page_bbox(i)
            ) for i in provider.page_range
        ]
        DocumentClass: Document = get_block_class(BlockTypes.Document)
        return DocumentClass(filepath=provider.filepath, pages=initial_pages)
