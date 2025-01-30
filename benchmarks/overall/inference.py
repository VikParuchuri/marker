import json
import tempfile
from bs4 import BeautifulSoup

from benchmarks.overall.scoring import score_blocks
from benchmarks.overall.schema import BlockScores
from marker.converters.pdf import PdfConverter

def get_marker_html(marker_models: dict, pdf_bytes: bytes):
    block_converter = PdfConverter(
        artifact_dict=marker_models,
        config={"page_range": [0], "disable_tqdm": True},
        renderer="marker.renderers.html.HTMLRenderer"
    )
    with tempfile.NamedTemporaryFile(suffix=".pdf", mode="wb") as f:
        f.write(pdf_bytes)
        rendered = block_converter(f.name)
    html = rendered.html
    soup = BeautifulSoup(html, "html.parser")
    inner_html = str(soup.find("body").decode_contents())
    return inner_html


def marker_html_func(model_dict, sample, **kwargs) -> BlockScores:
    gt_blocks = json.loads(sample["gt_blocks"])
    pdf_bytes = sample["pdf"]  # This is a single page PDF
    marker_html = get_marker_html(model_dict, pdf_bytes)
    gt_html = [block["html"] for block in gt_blocks]
    scores = score_blocks(gt_html, marker_html)
    return scores


def mathpix_html_func(model_dict, sample, mathpix_ds, **kwargs) -> BlockScores:
    uuid = sample["uuid"]
    data = None
    for row in mathpix_ds:
        if str(row["uuid"]) == str(uuid):
            data = row
            break
    if not data:
        raise ValueError(f"Could not find data for uuid {uuid}")

    mathpix_md = data["md"]
    gt_blocks = json.loads(sample["gt_blocks"])
    gt_html = [block["html"] for block in gt_blocks]
    scores = score_blocks(gt_html, mathpix_md, convert=False)
    return scores
