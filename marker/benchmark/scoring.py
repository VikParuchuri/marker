import math

from rapidfuzz import fuzz, distance
import re

CHUNK_MIN_CHARS = 25


def tokenize(text):
    # Combined pattern
    pattern = r'([^\w\s\d\'])|([\w\']+)|(\d+)|(\n+)|( +)'
    result = re.findall(pattern, text)
    # Flatten the result and filter out empty strings
    flattened_result = [item for sublist in result for item in sublist if item]
    return flattened_result


def chunk_text(text):
    chunks = text.split("\n")
    chunks = [c for c in chunks if c.strip() and len(c) > CHUNK_MIN_CHARS]
    return chunks


def overlap_score(hypothesis_chunks, reference_chunks):
    length_modifier = len(hypothesis_chunks) / len(reference_chunks)
    search_distance = max(len(reference_chunks) // 5, 10)
    chunk_scores = []
    chunk_weights = []
    for i, hyp_chunk in enumerate(hypothesis_chunks):
        max_score = 0
        chunk_weight = 1
        i_offset = int(i * length_modifier)
        chunk_range = range(max(0, i_offset-search_distance), min(len(reference_chunks), i_offset+search_distance))
        for j in chunk_range:
            ref_chunk = reference_chunks[j]
            score = fuzz.ratio(hyp_chunk, ref_chunk, score_cutoff=30) / 100
            if score > max_score:
                max_score = score
                chunk_weight = math.sqrt(len(ref_chunk))
        chunk_scores.append(max_score)
        chunk_weights.append(chunk_weight)
    chunk_scores = [chunk_scores[i] * chunk_weights[i] for i in range(len(chunk_scores))]
    return chunk_scores, chunk_weights


def score_text(hypothesis, reference):
    # Returns a 0-1 alignment score
    hypothesis_chunks = chunk_text(hypothesis)
    reference_chunks = chunk_text(reference)
    chunk_scores, chunk_weights = overlap_score(hypothesis_chunks, reference_chunks)
    return sum(chunk_scores) / sum(chunk_weights)