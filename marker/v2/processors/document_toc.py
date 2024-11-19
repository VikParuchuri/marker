from marker.v2.processors import BaseProcessor
from marker.v2.schema import BlockTypes
from marker.v2.schema.document import Document


class DocumentTOCProcessor(BaseProcessor):
    block_types = (BlockTypes.SectionHeader, )

    def __call__(self, document: Document):
        toc = []
        for page in document.pages:
            for block in page.children:
                if block.block_type not in self.block_types:
                    continue

                toc.append({
                    "title": block.raw_text(document).strip(),
                    "heading_level": block.heading_level,
                    "page_id": page.page_id,
                    "polygon": block.polygon.polygon
                })
        document.table_of_contents = toc