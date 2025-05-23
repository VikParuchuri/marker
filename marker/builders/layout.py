from typing import Annotated, List, Optional

from surya.layout import LayoutPredictor
from surya.layout.schema import LayoutResult, LayoutBox

from marker.builders import BaseBuilder
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.polygon import PolygonBox
from marker.schema.registry import get_block_class
from marker.settings import settings


class LayoutBuilder(BaseBuilder):
    """
    A builder for performing layout detection on PDF pages and merging the results into the document.
    """

    layout_batch_size: Annotated[
        Optional[int],
        "The batch size to use for the layout model.",
        "Default is None, which will use the default batch size for the model.",
    ] = None
    force_layout_block: Annotated[
        str,
        "Skip layout and force every page to be treated as a specific block type.",
    ] = None
    disable_tqdm: Annotated[
        bool,
        "Disable tqdm progress bars.",
    ] = False

    def __init__(self, layout_model: LayoutPredictor, config=None):
        self.layout_model = layout_model

        super().__init__(config)

    def __call__(self, document: Document, provider: PdfProvider):
        if self.force_layout_block is not None:
            # Assign the full content of every page to a single layout type
            layout_results = self.forced_layout(document.pages)
        else:
            layout_results = self.surya_layout(document.pages)
        self.add_blocks_to_pages(document.pages, layout_results)

    def get_batch_size(self):
        if self.layout_batch_size is not None:
            return self.layout_batch_size
        elif settings.TORCH_DEVICE_MODEL == "cuda":
            return 12
        return 6

    def forced_layout(self, pages: List[PageGroup]) -> List[LayoutResult]:
        layout_results = []
        for page in pages:
            layout_results.append(
                LayoutResult(
                    image_bbox=page.polygon.bbox,
                    bboxes=[
                        LayoutBox(
                            label=self.force_layout_block,
                            position=0,
                            top_k={self.force_layout_block: 1},
                            polygon=page.polygon.polygon,
                        ),
                    ],
                    sliced=False,
                )
            )
        return layout_results

    def surya_layout(self, pages: List[PageGroup]) -> List[LayoutResult]:
        self.layout_model.disable_tqdm = self.disable_tqdm
        layout_results = self.layout_model(
            [p.get_image(highres=False) for p in pages],
            batch_size=int(self.get_batch_size()),
        )
        return layout_results

    def add_blocks_to_pages(
        self, pages: List[PageGroup], layout_results: List[LayoutResult]
    ):
        for page, layout_result in zip(pages, layout_results):
            layout_page_size = PolygonBox.from_bbox(layout_result.image_bbox).size
            provider_page_size = page.polygon.size
            page.layout_sliced = (
                layout_result.sliced
            )  # This indicates if the page was sliced by the layout model
            for bbox in sorted(layout_result.bboxes, key=lambda x: x.position):
                block_cls = get_block_class(BlockTypes[bbox.label])
                layout_block = page.add_block(
                    block_cls, PolygonBox(polygon=bbox.polygon)
                )
                layout_block.polygon = layout_block.polygon.rescale(
                    layout_page_size, provider_page_size
                )
                layout_block.top_k = {
                    BlockTypes[label]: prob for (label, prob) in bbox.top_k.items()
                }
                page.add_structure(layout_block)

            # Ensure page has non-empty structure
            if page.structure is None:
                page.structure = []

            # Ensure page has non-empty children
            if page.children is None:
                page.children = []
