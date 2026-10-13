from typing import Annotated, Sequence

from marker.builders import BaseBuilder
from marker.builders.layout import LayoutBuilder
from marker.builders.line import LineBuilder
from marker.builders.ocr import OcrBuilder
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.registry import get_block_class


class DocumentBuilder(BaseBuilder):
    """
    Constructs a Document given a PdfProvider, LayoutBuilder, and OcrBuilder.
    """

    lowres_image_dpi: Annotated[
        int,
        "DPI setting for low-resolution page images used for layout detection.",
    ] = 96
    highres_image_dpi: Annotated[
        int,
        "DPI setting for high-resolution page images used for OCR.",
    ] = 192
    page_batch_size: Annotated[
        int, "Number of pages to build and OCR in each batch."
    ] = 30
    disable_ocr: Annotated[
        bool,
        "Disable OCR processing.",
    ] = False

    # Block types whose default-path processors crop the high-res image:
    # TableProcessor (Table/TableOfContents/Form) and EquationProcessor
    # (Equation/ChemicalBlock). Figures/Pictures/Diagrams are only consumed by
    # opt-in LLM processors, which are served by the per-page lazy loader, so
    # they are deliberately excluded here (a figure-only page skips the render).
    highres_block_types: Annotated[
        Sequence[BlockTypes],
        "Block types whose presence on a page requires the high-res image.",
    ] = (
        BlockTypes.Table,
        BlockTypes.Form,
        BlockTypes.TableOfContents,
        BlockTypes.Equation,
        BlockTypes.ChemicalBlock,
    )

    def __call__(
        self,
        provider: PdfProvider,
        layout_builder: LayoutBuilder,
        line_builder: LineBuilder,
        ocr_builder: OcrBuilder,
    ):
        if self.page_batch_size < 1:
            raise ValueError("page_batch_size must be at least 1")
        document = self.build_document(provider)
        for start in range(0, len(document.pages), self.page_batch_size):
            batch = document.model_copy(
                update={"pages": document.pages[start:start + self.page_batch_size]}
            )
            batch._page_index = None
            layout_builder(batch, provider)
            line_builder(batch, provider)
            # Render high-res only for pages that need OCR or table/equation crops.
            self.render_highres(batch, provider)
            if not self.disable_ocr:
                ocr_builder(batch, provider)
        return document

    def page_needs_highres(self, page: PageGroup) -> bool:
        if page.text_extraction_method == "surya":
            return True
        highres_types = set(self.highres_block_types)
        return any(block.block_type in highres_types for block in (page.children or []))

    def render_highres(self, document: Document, provider: PdfProvider):
        needed = [
            page
            for page in document.pages
            if page.highres_image is None and self.page_needs_highres(page)
        ]
        if not needed:
            return
        images = provider.get_images(
            [page.page_id for page in needed], self.highres_image_dpi
        )
        for page, image in zip(needed, images):
            page.highres_image = image

    def build_document(self, provider: PdfProvider):
        PageGroupClass: PageGroup = get_block_class(BlockTypes.Page)
        def make_loader(prov: PdfProvider):
            # Non-persistent: get_images opens/renders/closes per call.
            return lambda page_id: prov.get_images([page_id], self.highres_image_dpi)[0]

        loader = make_loader(provider)
        initial_pages = []
        for start in range(0, len(provider.page_range), self.page_batch_size):
            page_ids = provider.page_range[start:start + self.page_batch_size]
            lowres_images = provider.get_images(page_ids, self.lowres_image_dpi)
            for p, image in zip(page_ids, lowres_images):
                page = PageGroupClass(
                    page_id=p,
                    lowres_image=image,
                    highres_image=None,
                    polygon=provider.get_page_bbox(p),
                    refs=provider.get_page_refs(p),
                    pdftext_page=getattr(provider, "raw_pdftext_pages", {}).get(p),
                )
                page._highres_loader = loader
                initial_pages.append(page)
        DocumentClass: Document = get_block_class(BlockTypes.Document)
        return DocumentClass(filepath=provider.filepath, pages=initial_pages)
