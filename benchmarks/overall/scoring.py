import re
from bs4 import BeautifulSoup

from markdownify import markdownify as md
from rapidfuzz import fuzz

def standardize_html(html):
    soup = BeautifulSoup(html, "html.parser")

    # Convert all headers to h1 so we don't penalize small differences in header levels
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        tag.name = "h1"

    html = str(soup)
    markdown = md(html)
    markdown = markdown.replace("<br>", "\n")
    markdown = re.sub(r"\s+", " ", markdown)
    markdown = re.sub(r"\n+", "\n", markdown)
    markdown = re.sub("\\.+", ".", markdown) # Replace repeated periods with a single period, like in table of contents
    return markdown.strip()


def score_blocks(gt_html, method_html):
    scores = []
    for gt, method in zip(gt_html, method_html):
        gt= standardize_html(gt)
        method = standardize_html(method)
        score = fuzz.ratio(gt, method)
        scores.append(score)
    return scores