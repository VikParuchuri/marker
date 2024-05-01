from surya.languages import CODE_TO_LANGUAGE, LANGUAGE_TO_CODE


def replace_langs_with_codes(langs):
    for i, lang in enumerate(langs):
        if lang in LANGUAGE_TO_CODE:
            langs[i] = LANGUAGE_TO_CODE[lang]
    return langs


def validate_langs(langs):
    for lang in langs:
        if lang not in CODE_TO_LANGUAGE:
            raise ValueError(f"Invalid language code {lang}")