import os
import json

from pydantic import BaseModel
from marker.renderers.markdown import MarkdownOutput
from marker.renderers.html import HTMLOutput
from marker.renderers.json import JSONOutput


def save_output(rendered: BaseModel, output_dir: str, fname_base: str):
    if isinstance(rendered, MarkdownOutput):
        ext = "md"
        text = rendered.markdown
        images = rendered.images
    elif isinstance(rendered, HTMLOutput):
        ext = "html"
        text = rendered.html
        images = rendered.images
    elif isinstance(rendered, JSONOutput):
        ext = "json"
        text = rendered.model_dump_json(exclude=["metadata"], indent=2)
        images = {}
    else:
        raise ValueError("Invalid output type")

    with open(os.path.join(output_dir, f"{fname_base}.{ext}"), "w+") as f:
        f.write(text)
    with open(os.path.join(output_dir, f"{fname_base}_meta.json"), "w+") as f:
        f.write(json.dumps(rendered.metadata, indent=2))

    for img_name, img in images.items():
        img.save(os.path.join(output_dir, img_name), "PNG")