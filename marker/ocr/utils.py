from nltk import wordpunct_tokenize
from spellchecker import SpellChecker
from marker.settings import settings


def detect_bad_ocr(text, spell_lang: str | None, misspell_threshold=.8, space_threshold=.5, newline_threshold=.3, alphanum_threshold=.5):
    if len(text) == 0:
        # Assume OCR failed if we have no text
        return True

    words = wordpunct_tokenize(text)
    words = [w for w in words if w.strip()]
    alpha_words = [word for word in words if word.isalnum()]
    nonalpha_words = [word for word in words if not word.isalnum()]

    if spell_lang:
        spell = SpellChecker(language=spell_lang)
        misspelled = spell.unknown(alpha_words)
        if len(misspelled) + len(nonalpha_words) > len(words) * misspell_threshold:
            return True
    spaces = text.count(" ")
    # More than 50% of chars are spaces
    if spaces / len(text) > space_threshold:
        return True

    newlines = text.count("\n")
    # More than 30% of chars are newlines
    if newlines / len(text) > newline_threshold:
        return True

    if alphanum_ratio(text) < alphanum_threshold: # Garbled text
        return True

    invalid_chars = 0
    for char in text:
        if char in settings.INVALID_CHARS:
            invalid_chars += 1

    if invalid_chars > 2:
        return True

    return False


def font_flags_decomposer(flags):
    """Make font flags human readable."""
    l = []
    if flags & 2 ** 0:
        l.append("superscript")
    if flags & 2 ** 1:
        l.append("italic")
    if flags & 2 ** 2:
        l.append("serifed")
    else:
        l.append("sans")
    if flags & 2 ** 3:
        l.append("monospaced")
    else:
        l.append("proportional")
    if flags & 2 ** 4:
        l.append("bold")
    return "_".join(l)


def alphanum_ratio(text):
    alphanumeric_count = sum([1 for c in text if c.isalnum()])

    if len(text) == 0:
        if alphanumeric_count == 0:
            return 1
        else:
            return 0

    ratio = alphanumeric_count / len(text)
    return ratio
