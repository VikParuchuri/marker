from rapidfuzz import fuzz
import re


def split_to_cells(table):
    table = table.strip()
    table = re.sub(r" {2,}", "", table)
    table_rows = table.split("\n")
    table_rows = [t for t in table_rows if t.strip()]
    table_cells = [r.split("|") for r in table_rows]
    return table_cells


def align_rows(hypothesis, ref_row):
    best_alignment = []
    best_alignment_score = 0
    for j in range(0, len(hypothesis)):
        alignments = []
        for i in range(len(ref_row)):
            if i >= len(hypothesis[j]):
                alignments.append(0)
                continue
            alignment = fuzz.ratio(hypothesis[j][i], ref_row[i], score_cutoff=30) / 100
            alignments.append(alignment)
        if len(alignments) == 0:
            continue
        alignment_score = sum(alignments) / len(alignments)
        if alignment_score >= best_alignment_score:
            best_alignment = alignments
            best_alignment_score = alignment_score
    return best_alignment


def score_table(hypothesis, reference):
    hypothesis = split_to_cells(hypothesis)
    reference = split_to_cells(reference)

    alignments = []
    for i in range(0, len(reference)):
        alignments.extend(align_rows(hypothesis, reference[i]))
    return sum(alignments) / len(alignments)