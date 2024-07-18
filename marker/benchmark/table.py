from rapidfuzz import fuzz
import re


def split_to_rows(table):
    table = table.strip()
    table = re.sub(r" {2,}", "", table)
    table_rows = table.split("\n")
    return [t for t in table_rows if t.strip()]


def score_table(hypothesis, reference):
    hypothesis = split_to_rows(hypothesis)
    reference = split_to_rows(reference)

    alignments = []
    for row in reference:
        max_alignment = 0
        for hrow in hypothesis:
            alignment = fuzz.ratio(hrow, row, score_cutoff=30) / 100
            if alignment > max_alignment:
                max_alignment = alignment
        alignments.append(max_alignment)
    return sum(alignments) / len(reference)