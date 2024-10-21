import requests
from PIL import ImageDraw, ImageFont, Image

from marker.settings import settings
import os


def get_font_path() -> str:
    font_path = settings.DEBUG_RENDER_FONT

    if not os.path.exists(font_path):
        os.makedirs(os.path.dirname(font_path), exist_ok=True)
        font_dl_path = f"{settings.FONT_DL_BASE}/{os.path.basename(font_path)}"
        with requests.get(font_dl_path, stream=True) as r, open(font_path, 'wb') as f:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    return font_path


def get_text_size(text, font):
    im = Image.new(mode="P", size=(0, 0))
    draw = ImageDraw.Draw(im)
    _, _, width, height = draw.textbbox((0, 0), text=text, font=font)
    return width, height


def render_on_image(bboxes, image, labels=None, label_offset=1, label_font_size=10, color: str | list='red', draw_bbox=True):
    draw = ImageDraw.Draw(image)
    font_path = get_font_path()
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
            text_size = get_text_size(label, label_font)
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