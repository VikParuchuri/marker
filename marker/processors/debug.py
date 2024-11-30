import json
import os

import requests
from PIL import Image, ImageDraw, ImageFont

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.settings import settings


class DebugProcessor(BaseProcessor):
    """
    A processor for debugging the document.

    Attributes:
        debug_data_folder (str):
            The folder to dump debug data to.
            Default is "debug_data".

        debug_layout_images (bool):
            Whether to dump layout debug images.
            Default is False.

        debug_pdf_images (bool):
            Whether to dump PDF debug images.
            Default is False.

        debug_json (bool):
            Whether to dump block debug data.
            Default is False.

        render_font (str):
            The path to the font to use for rendering debug images.
            Default is "GoNotoCurrent-Regular.ttf" in the FONT_DIR folder.

        font_dl_path (str):
            The path to download the font from.
            Default is "https://github.com/satbyy/go-noto-universal/releases/download/v7.0".
    """
    block_types = tuple()
    debug_data_folder: str = "debug_data"
    debug_layout_images: bool = False
    debug_pdf_images: bool = False
    debug_json: bool = False
    render_font: str = os.path.join(settings.FONT_DIR, "GoNotoCurrent-Regular.ttf")
    font_dl_path: str = "https://github.com/satbyy/go-noto-universal/releases/download/v7.0"

    def __call__(self, document: Document):
        # Remove extension from doc name
        doc_base = os.path.basename(document.filepath).rsplit(".", 1)[0]
        self.debug_folder = os.path.join(self.debug_data_folder, doc_base)
        if any([self.debug_layout_images, self.debug_pdf_images, self.debug_json]):
            os.makedirs(self.debug_folder, exist_ok=True)

        document.debug_data_path = self.debug_folder

        if self.debug_layout_images:
            self.draw_layout_debug_images(document)
            print(f"Dumped layout debug images to {self.debug_data_folder}")

        if self.debug_pdf_images:
            self.draw_pdf_debug_images(document)
            print(f"Dumped PDF debug images to {self.debug_data_folder}")

        if self.debug_json:
            self.dump_block_debug_data(document)
            print(f"Dumped block debug data to {self.debug_data_folder}")

    def draw_pdf_debug_images(self, document: Document):
        for page in document.pages:
            png_image = page.highres_image.copy()

            line_bboxes = []
            span_bboxes = []
            for child in page.children:
                if child.block_type == BlockTypes.Line:
                    bbox = child.polygon.rescale(page.polygon.size, png_image.size).bbox
                    line_bboxes.append(bbox)
                elif child.block_type == BlockTypes.Span:
                    bbox = child.polygon.rescale(page.polygon.size, png_image.size).bbox
                    span_bboxes.append(bbox)

            self.render_on_image(line_bboxes, png_image, color="blue", draw_bbox=True, label_font_size=24)
            self.render_on_image(span_bboxes, png_image, color="green", draw_bbox=True, label_font_size=24)

            png_image = self.render_layout_boxes(page, png_image)

            debug_file = os.path.join(self.debug_folder, f"pdf_page_{page.page_id}.png")
            png_image.save(debug_file)


    def draw_layout_debug_images(self, document: Document, pdf_mode=False):
        for page in document.pages:
            img_size = page.highres_image.size
            png_image = Image.new("RGB", img_size, color="white")

            line_bboxes = []
            line_text = []
            for child in page.children:
                if child.block_type != BlockTypes.Line:
                    continue

                bbox = child.polygon.rescale(page.polygon.size, img_size).bbox
                line_bboxes.append(bbox)
                line_text.append(child.raw_text(document))

            self.render_on_image(line_bboxes, png_image, labels=line_text, color="black", draw_bbox=False, label_font_size=24)

            png_image = self.render_layout_boxes(page, png_image)

            debug_file = os.path.join(self.debug_folder, f"layout_page_{page.page_id}.png")
            png_image.save(debug_file)


    def render_layout_boxes(self, page, png_image):
        layout_bboxes = []
        layout_labels = []
        for block_id in page.structure:
            child = page.get_block(block_id)
            if child.block_type in [BlockTypes.Line, BlockTypes.Span]:
                continue

            bbox = child.polygon.rescale(page.polygon.size, png_image.size).bbox
            layout_bboxes.append(bbox)
            layout_labels.append(str(child.block_type))

        self.render_on_image(layout_bboxes, png_image, labels=layout_labels, color="red", label_font_size=24)

        order_labels = [str(i) for i in range(len(layout_bboxes))]
        self.render_on_image(
            layout_bboxes,
            png_image,
            labels=order_labels,
            color="green",
            draw_bbox=False,
            label_offset=5,
            label_font_size=24
        )
        return png_image

    def dump_block_debug_data(self, document: Document):
        debug_file = os.path.join(self.debug_folder, f"blocks.json")
        debug_data = []
        for page in document.pages:
            page_data = page.model_dump(exclude=["lowres_image", "highres_image"])
            debug_data.append(page_data)

        with open(debug_file, "w+") as f:
            json.dump(debug_data, f)

    def get_font_path(self) -> str:
        if not os.path.exists(self.render_font):
            os.makedirs(os.path.dirname(self.render_font), exist_ok=True)
            font_dl_path = f"{self.font_dl_path}/{os.path.basename(self.render_font)}"
            with requests.get(font_dl_path, stream=True) as r, open(self.render_font, 'wb') as f:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        return self.render_font

    def get_text_size(self, text, font):
        im = Image.new(mode="P", size=(0, 0))
        draw = ImageDraw.Draw(im)
        _, _, width, height = draw.textbbox((0, 0), text=text, font=font)
        return width, height

    def render_on_image(self, bboxes, image, labels=None, label_offset=1, label_font_size=10, color: str | list = 'red', draw_bbox=True):
        draw = ImageDraw.Draw(image)
        font_path = self.get_font_path()
        label_font = ImageFont.truetype(font_path, label_font_size)

        for i, bbox in enumerate(bboxes):
            bbox = [int(p) for p in bbox]
            if draw_bbox:
                draw.rectangle(bbox, outline=color[i] if isinstance(color, list) else color, width=1)

            if labels is not None:
                label = labels[i]
                text_position = (
                    bbox[0] + label_offset,
                    bbox[1] + label_offset
                )
                text_size = self.get_text_size(label, label_font)
                if text_size[0] <= 0 or text_size[1] <= 0:
                    continue
                box_position = (
                    text_position[0],
                    text_position[1],
                    text_position[0] + text_size[0],
                    text_position[1] + text_size[1]
                )
                draw.rectangle(box_position, fill="white")
                draw.text(
                    text_position,
                    label,
                    fill=color[i] if isinstance(color, list) else color,
                    font=label_font
                )

        return image
