"""Render validated table JSON; the model does not generate the HTML."""

import re
from math import ceil, floor
from html import escape

from marker.settings import settings


def text_html(text):
    result = []
    parts = re.split(r"(?<!\\)(?:\\\\)*\$", text)
    for i, part in enumerate(parts):
        if i % 2:
            result.append("<math>" + escape(part) + "</math>")
        else:
            result.append(escape(part).replace("\n", "<br>"))
    return "".join(result)


def render_table(table, images, block, extract_images=True):
    embedded, exported = {}, table.model_dump()
    html = ["<table>"]
    if table.caption_blocks:
        html.append("<caption>" + text_html(table.caption_raw) + "</caption>")
    html.append("<tbody>")
    for r in range(table.n_rows):
        html.append("<tr>")
        for cell in sorted((c for c in table.cells if c.r == r), key=lambda c: c.c):
            tag = "th" if cell.role == "header" else "td"
            html.append(f'<{tag} rowspan="{cell.rowspan}" colspan="{cell.colspan}">')
            html.append(text_html(cell.text))
            for fi, figure in enumerate(cell.figures):
                if not extract_images:
                    continue
                image = images[figure.region_id]
                x0, y0, x1, y1 = figure.bbox
                crop = image.crop((floor(x0), floor(y0), ceil(x1), ceil(y1)))
                name = f"{block.id.to_path()}_r{cell.r}_c{cell.c}_{fi}.{settings.OUTPUT_IMAGE_FORMAT.lower()}"
                embedded[name] = crop
                html.append(f'<img src="{name}" alt="{escape(figure.description, quote=True)}">')
                target = next(c for c in exported["cells"] if c["r"] == cell.r and c["c"] == cell.c)
                target["figures"][fi]["src"] = name
            html.append(f"</{tag}>")
        html.append("</tr>")
    html.append("</tbody></table>")
    for note in table.notes:
        text = note.text
        if note.marker and not text.lstrip().startswith(note.marker):
            text = note.marker + " " + text
        html.append('<p class="table-note">' + text_html(text) + "</p>")
    if table.amendment_note and table.amendment_blocks:
        html.append("<p>" + text_html(table.amendment_note) + "</p>")
    return "".join(html), embedded, exported
