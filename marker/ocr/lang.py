from surya.languages import CODE_TO_LANGUAGE, LANGUAGE_TO_CODE

from marker.ocr.tesseract import LANGUAGE_TO_TESSERACT_CODE, TESSERACT_CODE_TO_LANGUAGE
from marker.settings import settings


def replace_langs_with_codes(langs):
    if settings.OCR_ENGINE == "surya":
        for i, lang in enumerate(langs):
            if lang in LANGUAGE_TO_CODE:
                langs[i] = LANGUAGE_TO_CODE[lang]
    else:
        for i, lang in enumerate(langs):
            if lang in LANGUAGE_TO_CODE:
                langs[i] = LANGUAGE_TO_TESSERACT_CODE[lang]
    return langs


def validate_langs(langs):
    if settings.OCR_ENGINE == "surya":
        for lang in langs:
            if lang not in CODE_TO_LANGUAGE:
                raise ValueError(f"Invalid language code {lang} for Surya OCR")
    else:
        for lang in langs:
            if lang not in TESSERACT_CODE_TO_LANGUAGE:
                raise ValueError(f"Invalid language code {lang} for Tesseract")