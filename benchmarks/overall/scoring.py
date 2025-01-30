from typing import List

from rapidfuzz import fuzz

from benchmarks.overall.schema import BlockScores
from marker.renderers.markdown import MarkdownRenderer
import re


def kendall_tau(correct_order: List[int], actual_order: List[int]) -> float:
    n = len(correct_order)
    concordant = 0
    discordant = 0

    for i in range(n):
        for j in range(i + 1, n):
            correct_sign = correct_order[i] - correct_order[j]
            actual_sign = actual_order[i] - actual_order[j]

            if (correct_sign > 0 and actual_sign > 0) or (correct_sign < 0 and actual_sign < 0):
                concordant += 1
            elif (correct_sign < 0 and actual_sign > 0) or (correct_sign > 0 and actual_sign < 0):
                discordant += 1

    total_pairs = (n * (n - 1)) // 2
    tau = (concordant - discordant) / total_pairs
    tau = (tau + 1) / 2 # 0-1 scale
    return tau * 100 # 0-100 scale


def find_fuzzy_alignments(
        main_string: str,
        substrings: List[str],
        threshold: int = 70
) -> List[dict]:
    alignments = []

    for idx, substr in enumerate(substrings):
        result = fuzz.partial_ratio_alignment(substr, main_string, score_cutoff=threshold)

        score = 0
        dest_start = 0
        dest_end = 0
        if result:
            score = result.score
            dest_start = result.dest_start
            dest_end = result.dest_end

        alignments.append({
            "string": substr,
            "start": dest_start,
            "end": dest_end,
            "score": score,
            "idx": idx
        })
    return alignments

def convert_to_md(html):
    md = MarkdownRenderer()
    markdown = md.md_cls.convert(html)
    return markdown

def standardize_markdown(markdown):
    pattern = r'(?<!\\)\$(?:\$([^$]+)\$\$|\s*([^$\n]+?)\s*\$)'
    markdown = re.sub(pattern, standardize_math, markdown)

    markdown = markdown.replace("<br>", "\n")
    markdown = re.sub(r"<sub>(.*?)</sub>", r"\1", markdown)
    markdown = re.sub(r"<sup>(.*?)</sup>", r"\1", markdown)

    markdown = re.sub(r"\s+", " ", markdown)
    markdown = re.sub(r"\n+", "\n", markdown)
    markdown = re.sub("\\.+", ".", markdown) # Replace repeated periods with a single period, like in table of contents
    markdown = re.sub("#+", "#", markdown) # Replace repeated headers with a single header
    markdown = re.sub(r"\$", "", markdown) # Remove equation delimiters
    return markdown.strip().lower()


def standardize_math(match):
    try:
        delim = "$$" if match.group(0).startswith('$$') else "$"
        math_content = match.group(1) or match.group(2)
        result = clean_latex(math_content)
        return f'{delim}{result}{delim}'
    except Exception as e:
        print(f"Failed to standardize math expression: {match.group(0)} with error: {e}")
        return match.group(0)


def clean_latex(latex_str):
    latex_str = re.sub(r'\s+', ' ', latex_str.strip())
    for tag in [r'\\text', r'\\mathrm', r'\\mathbf', r'\\textbf']:
        latex_str = re.sub(tag + r'\{([^}]+)\}', r'\1', latex_str)


    replacements = {
        '\\times': '*',
        '\\cdot': '*',
        '\\div': '/',
        '\\le': '<=',
        '\\ge': '>=',
        '\\neq': '!=',
        '\\to': '\\rightarrow',
    }

    for old, new in replacements.items():
        latex_str = latex_str.replace(old, new)

    return latex_str


def score_blocks(gt_html, method_html, convert=True) -> BlockScores:
    if convert:
        method_html = convert_to_md(method_html)
    method_html = standardize_markdown(method_html)
    gt = [standardize_markdown(convert_to_md(gt)) for gt in gt_html]
    alignments = find_fuzzy_alignments(method_html, gt)
    scores = [alignment["score"] for alignment in alignments]
    orders = [alignment["start"] for alignment in alignments]
    correct_order = range(len(gt))
    actual_order = sorted(range(len(gt)), key=lambda x: orders[x])
    order_score = kendall_tau(correct_order, actual_order)
    gt_weights = [len(g) for g in gt]
    weighted_scores = [score * weight for score, weight in zip(scores, gt_weights)]

    # Weight the score by sequence length
    overall_score = sum(weighted_scores) / max(1, sum(gt_weights))
    overall_score = overall_score * 0.8 + order_score * 0.2
    return {
        "scores": scores,
        "order_score": order_score,
        "gt": gt,
        "method": method_html,
        "overall_score": overall_score
    }