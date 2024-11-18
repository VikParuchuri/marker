from bs4 import BeautifulSoup
from pydantic import BaseModel

from marker.v2.renderers import BaseRenderer
from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import BlockId


class HTMLOutput(BaseModel):
    html: str
    images: dict


class HTMLRenderer(BaseRenderer):
    remove_blocks: list = [BlockTypes.PageHeader, BlockTypes.PageFooter]
    image_blocks: list = [BlockTypes.Picture, BlockTypes.Figure]

    def extract_image(self, document, image_id):
        image_block = document.get_block(image_id)
        page = document.get_page(image_block.page_id)
        page_img = page.highres_image
        image_box = image_block.polygon.rescale(page.polygon.size, page_img.size)
        cropped = page_img.crop(image_box.bbox)
        return cropped

    def extract_html(self, document, document_output):
        soup = BeautifulSoup(document_output.html, 'html.parser')

        content_refs = soup.find_all('content-ref')
        ref_block_id = None
        images = {}
        for ref in content_refs:
            src = ref.get('src')
            sub_images = {}
            for item in document_output.children:
                if item.id == src:
                    content, sub_images = self.extract_html(document, item)
                    ref_block_id: BlockId = item.id
                    break

            if ref_block_id.block_type in self.remove_blocks:
                ref.replace_with('')
            elif ref_block_id.block_type in self.image_blocks:
                image = self.extract_image(document, ref_block_id)
                image_name = f"{ref_block_id.to_path()}.png"
                images[image_name] = image
                ref.replace_with(BeautifulSoup(f"<p><img src='{image_name}'></p>", 'html.parser'))
            else:
                images.update(sub_images)
                ref.replace_with(BeautifulSoup(f"<div>{content}</div>", 'html.parser'))

        return str(soup), images

    def __call__(self, document) -> HTMLOutput:
        document_output = document.render()
        full_html, images = self.extract_html(document, document_output)
        return HTMLOutput(
            html=full_html,
            images=images,
        )
