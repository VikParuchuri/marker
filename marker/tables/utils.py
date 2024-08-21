import re


def sort_table_blocks(blocks, tolerance=5):
    vertical_groups = {}
    for block in blocks:
        if hasattr(block, "bbox"):
            bbox = block.bbox
        else:
            bbox = block["bbox"]
        group_key = round(bbox[1] / tolerance)
        if group_key not in vertical_groups:
            vertical_groups[group_key] = []
        vertical_groups[group_key].append(block)

    # Sort each group horizontally and flatten the groups into a single list
    sorted_blocks = []
    for _, group in sorted(vertical_groups.items()):
        sorted_group = sorted(group, key=lambda x: x.bbox[0] if hasattr(x, "bbox") else x["bbox"][0])
        sorted_blocks.extend(sorted_group)

    return sorted_blocks


def replace_dots(text):
    dot_pattern = re.compile(r'(\s*\.\s*){4,}')
    dot_multiline_pattern = re.compile(r'.*(\s*\.\s*){4,}.*', re.DOTALL)

    if dot_multiline_pattern.match(text):
        text = dot_pattern.sub(' ', text)
    return text


def replace_newlines(text):
    # Replace all newlines
    newline_pattern = re.compile(r'[\r\n]+')
    return newline_pattern.sub(' ', text.strip())

import PIL
from marker.tables.schema import Rectangle

def save_table_image(page_img: PIL.Image, box: Rectangle, output_path: str, padding=30):
    """Convert the tensor to a list of Python floats and then to integers"""
    padding = 30

    # box = [int(coord) for coord in box.tolist()]

    # Crop format: (left, upper, right, lower)
    # left, upper, right, lower = box
    cropped_image = page_img.crop(
        (
            box.left - padding,
            box.top - padding,
            box.right + padding,
            box.bottom + padding,
        )
    )
    cropped_image.save(output_path)
    return output_path