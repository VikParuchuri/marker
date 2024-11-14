from marker.settings import settings
from marker.v2.builders import BaseBuilder
from marker.v2.builders.layout import LayoutBuilder
from marker.v2.providers.pdf import PdfProvider
from marker.v2.schema.document import Document
from marker.v2.schema.groups.page import PageGroup
from marker.v2.schema.polygon import PolygonBox


class DocumentBuilder(BaseBuilder):
    def __call__(self, provider: PdfProvider, layout_builder: LayoutBuilder):
        document = self.build_document(provider)
        layout_builder(document, provider)
        return document

    def build_document(self, provider: PdfProvider):
        if provider.config.page_range is None:
            page_range = range(len(provider))
        else:
            page_range = provider.config.page_range
            assert max(page_range) < len(provider) and min(page_range) >= 0, "Invalid page range"

        initial_pages = [
            PageGroup(
                page_id=i,
                lowres_image=provider.get_image(i, settings.IMAGE_DPI),
                highres_image=provider.get_image(i, settings.HIGHRES_IMAGE_DPI),
                polygon=PolygonBox.from_bbox(provider.get_page_bbox(i))
            ) for i in page_range
        ]

        return Document(filepath=provider.filepath, pages=initial_pages)
