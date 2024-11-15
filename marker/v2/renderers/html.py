from bs4 import BeautifulSoup
from marker.v2.renderers import BaseRenderer
from marker.v2.schema import BlockTypes


class HTMLRenderer(BaseRenderer):
    remove_blocks: list = [BlockTypes.PageHeader, BlockTypes.PageFooter]
    def extract_html(self, document_output):
        soup = BeautifulSoup(document_output.html, 'html.parser')

        content_refs = soup.find_all('content-ref')
        ref_block_type = None
        for ref in content_refs:
            src = ref.get('src')
            for item in document_output.children:
                if item.id == src:
                    content = self.extract_html(item)
                    ref_block_type = item.id.block_type
                    break

            if ref_block_type in self.remove_blocks:
                ref.replace_with('')
            else:
                ref.replace_with(BeautifulSoup(f"<div>{content}</div>", 'html.parser'))

        return str(soup)

    def __call__(self, document_output):
        full_html = self.extract_html(document_output)
        return full_html
