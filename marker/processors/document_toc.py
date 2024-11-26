from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document


class DocumentTOCProcessor(BaseProcessor):
    """
    A processor for generating a table of contents for the document.
    """
    block_types = (BlockTypes.SectionHeader, )

    def __call__(self, document: Document):
        toc = []
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                toc.append({
                    "title": block.raw_text(document).strip(),
                    "heading_level": block.heading_level,
                    "page_id": page.page_id,
                    "polygon": block.polygon.polygon
                })
        document.table_of_contents = toc
