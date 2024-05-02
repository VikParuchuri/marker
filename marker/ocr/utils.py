from typing import Optional


def font_flags_decomposer(flags: Optional[int]) -> str:
    if flags is None:
        return ""

    flag_descriptions = []
    if flags & (1 << 0):  # PDFFONT_FIXEDPITCH
        flag_descriptions.append("fixed_pitch")
    if flags & (1 << 1):  # PDFFONT_SERIF
        flag_descriptions.append("serif")
    if flags & (1 << 2):  # PDFFONT_SYMBOLIC
        flag_descriptions.append("symbolic")
    if flags & (1 << 3):  # PDFFONT_SCRIPT
        flag_descriptions.append("script")
    if flags & (1 << 5):  # PDFFONT_NONSYMBOLIC
        flag_descriptions.append("non_symbolic")
    if flags & (1 << 6):  # PDFFONT_ITALIC
        flag_descriptions.append("italic")
    if flags & (1 << 16): # PDFFONT_ALLCAP
        flag_descriptions.append("all_cap")
    if flags & (1 << 17): # PDFFONT_SMALLCAP
        flag_descriptions.append("small_cap")
    if flags & (1 << 18): # PDFFONT_FORCEBOLD
        flag_descriptions.append("bold")
    if flags & (1 << 19): # PDFFONT_USEEXTERNATTR
        flag_descriptions.append("use_extern_attr")

    return "_".join(flag_descriptions)


def alphanum_ratio(text):
    text = text.replace(" ", "")
    text = text.replace("\n", "")
    alphanumeric_count = sum([1 for c in text if c.isalnum()])

    if len(text) == 0:
        return 1

    ratio = alphanumeric_count / len(text)
    return ratio
