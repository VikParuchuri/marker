from marker.settings import settings
from marker.v2.builders import BaseBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.builders.ocr import OcrBuilder
from marker.v2.providers.pdf import PdfProvider
from marker.v2.schema.document import Document
from marker.v2.schema.groups.page import PageGroup
from marker.v2.schema.registry import get_block_cls


class DocumentBuilder(BaseBuilder):
    def __call__(self, provider: PdfProvider, layout_builder: LayoutBuilder, ocr_builder: OcrBuilder):
        document = self.build_document(provider)
        layout_builder(document, provider)
        ocr_builder(document, provider)
        return document

    def build_document(self, provider: PdfProvider):
        PageGroupClass = get_block_cls(PageGroup)
        initial_pages = [
            PageGroupClass(
                page_id=i,
                lowres_image=provider.get_image(i, settings.IMAGE_DPI),
                highres_image=provider.get_image(i, settings.HIGHRES_IMAGE_DPI),
                polygon=provider.get_page_bbox(i)
            ) for i in provider.page_range
        ]
        DocumentClass = get_block_cls(Document)
        return DocumentClass(filepath=provider.filepath, pages=initial_pages)
