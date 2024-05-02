from marker.schema.page import Page


def find_headings(page: Page):
    headings = []
    font_info = {
        "title_font_size": [],
        "title_font_weight": [],
        "section_font_size": [],
        "section_font_weight": [],
        "title_font": [],
        "section_font": [],
    }

    for block in page.blocks:
        if block.block_type in ["Title" or "Section-header"]:
            info_type = "title" if block.block_type == "Title" else "section"
            for keys in ["font", "font_size", "font_weight"]:
                font_info[f"{info_type}_{keys}"].append(block.font_info(keys))
    for key in font_info.keys():
        font_info[key] = [f for f in font_info[key] if f is not None]
    return headings