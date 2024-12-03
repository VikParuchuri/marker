from typing import Literal

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from pydantic import BaseModel

from marker.renderers import BaseRenderer
from marker.schema import BlockTypes
from marker.schema.blocks import BlockId
from marker.settings import settings

# Ignore beautifulsoup warnings
import warnings
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

# Suppress DecompressionBombError
from PIL import Image
Image.MAX_IMAGE_PIXELS = None


class HTMLOutput(BaseModel):
    html: str
    images: dict
    metadata: dict


class HTMLRenderer(BaseRenderer):
    page_blocks: list = [BlockTypes.Page]
    paginate_output: bool = False
    image_extraction_mode: Literal["lowres", "highres"] = "highres"

    def extract_image(self, document, image_id):
        image_block = document.get_block(image_id)
        page = document.get_page(image_block.page_id)
        page_img = page.lowres_image if self.image_extraction_mode == "lowres" else page.highres_image
        image_box = image_block.polygon.rescale(page.polygon.size, page_img.size)
        cropped = page_img.crop(image_box.bbox)
        return cropped

    def extract_html(self, document, document_output, level=0):
        soup = BeautifulSoup(document_output.html, 'html.parser')

        content_refs = soup.find_all('content-ref')
        ref_block_id = None
        images = {}
        for ref in content_refs:
            src = ref.get('src')
            sub_images = {}
            for item in document_output.children:
                if item.id == src:
                    content, sub_images_ = self.extract_html(document, item, level + 1)
                    sub_images.update(sub_images_)
                    ref_block_id: BlockId = item.id
                    break

            if ref_block_id.block_type in self.remove_blocks:
                ref.replace_with('')
            elif ref_block_id.block_type in self.image_blocks:
                if self.extract_images:
                    image = self.extract_image(document, ref_block_id)
                    image_name = f"{ref_block_id.to_path()}.{settings.OUTPUT_IMAGE_FORMAT.lower()}"
                    images[image_name] = image
                    ref.replace_with(BeautifulSoup(f"<p><img src='{image_name}'></p>", 'html.parser'))
                else:
                    ref.replace_with('')
            elif ref_block_id.block_type in self.page_blocks:
                images.update(sub_images)
                if self.paginate_output:
                    content = f"<div class='page' data-page-id='{ref_block_id.page_id}'>{content}</div>"
                ref.replace_with(BeautifulSoup(f"{content}", 'html.parser'))
            else:
                images.update(sub_images)
                ref.replace_with(BeautifulSoup(f"{content}", 'html.parser'))

        output = str(soup)
        if level == 0:
            output = self.merge_consecutive_tags(output, 'b')
            output = self.merge_consecutive_tags(output, 'i')

        return output, images

    def __call__(self, document) -> HTMLOutput:
        document_output = document.render()
        full_html, images = self.extract_html(document, document_output)
        return HTMLOutput(
            html=full_html,
            images=images,
            metadata=self.generate_document_metadata(document, document_output)
        )
