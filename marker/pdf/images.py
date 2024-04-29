import pypdfium2 as pdfium


def render_image(page: pdfium.PdfPage, dpi):
    image = page.render(
        scale=dpi / 72,
        draw_annots=False
    ).to_pil()
    image = image.convert("RGB")
    return image