import tempfile
import time

from benchmarks.overall.clean import clean_input
from benchmarks.overall.schema import BlockScores
from benchmarks.overall.scoring import score_blocks
from marker.converters.pdf import PdfConverter

def get_marker_markdown(marker_models: dict, pdf_bytes: bytes, use_llm: bool):
    block_converter = PdfConverter(
        artifact_dict=marker_models,
        config={"page_range": [0], "disable_tqdm": True, "use_llm": use_llm}
    )

    with tempfile.NamedTemporaryFile(suffix=".pdf", mode="wb") as f:
        f.write(pdf_bytes)
        rendered = block_converter(f.name)

    return rendered.markdown


def marker_scoring_func(model_dict, sample, gt_markdown, use_llm=False, **kwargs) -> BlockScores:
    pdf_bytes = sample["pdf"]  # This is a single page PDF
    start = time.time()
    marker_md = get_marker_markdown(model_dict, pdf_bytes, use_llm)
    marker_md = clean_input(marker_md)
    total = time.time() - start
    scores = score_blocks(gt_markdown, marker_md)
    scores["time"] = total
    scores["markdown"] = marker_md
    return scores


def mathpix_scoring_func(model_dict, sample, gt_markdown, mathpix_ds=None, **kwargs) -> BlockScores:
    uuid = sample["uuid"]
    data = None
    for row in mathpix_ds:
        if str(row["uuid"]) == str(uuid):
            data = row
            break
    if not data:
        raise ValueError(f"Could not find data for uuid {uuid}")

    mathpix_md = clean_input(data["md"])
    scores = score_blocks(gt_markdown, mathpix_md)
    scores["time"] = data["time"]
    scores["markdown"] = mathpix_md
    return scores
