from bs4 import BeautifulSoup
from markdownify import markdownify
from marker.v2.renderers import BaseRenderer


class MarkdownRenderer(BaseRenderer):
    def extract_html(self, document_output):
        soup = BeautifulSoup(document_output.html, 'html.parser')

        content_refs = soup.find_all('content-ref')
        for ref in content_refs:
            src = ref.get('src')
            for item in document_output.children:
                if item.id == src:
                    content = self.extract_html(item)
                    break

            ref.replace_with(BeautifulSoup(content, 'html.parser'))

        return str(soup)

    def __call__(self, document_output):
        full_html = self.extract_html(document_output)
        return markdownify(full_html)


