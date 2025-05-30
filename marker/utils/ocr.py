from typing import List
from surya.ocr_error import OCRErrorPredictor

from marker.providers import ProviderPageLines
from marker.schema.groups.page import PageGroup


def detect_ocr_errors(
    pages: List[PageGroup],
    provider_page_lines: ProviderPageLines,
    ocr_error_model: OCRErrorPredictor,
    batch_size: int,
    disable_tqdm: bool = False,
):
    page_texts = []
    for document_page in pages:
        provider_lines = provider_page_lines.get(document_page.page_id, [])
        page_text = "\n".join(
            " ".join(s.text for s in line.spans) for line in provider_lines
        )
        page_texts.append(page_text)

    ocr_error_model.disable_tqdm = disable_tqdm
    ocr_error_detection_results = ocr_error_model(page_texts, batch_size=batch_size)
    return ocr_error_detection_results
