import math

from rapidfuzz import fuzz
import re
import regex

CHUNK_MIN_CHARS = 25


def tokenize(text):
    # Combined pattern
    pattern = r'([^\w\s\d\'])|([\w\']+)|(\d+)|(\n+)|( +)'
    result = re.findall(pattern, text)
    # Flatten the result and filter out empty strings
    flattened_result = [item for sublist in result for item in sublist if item]
    return flattened_result


def replace_non_alphanumeric(text):
    return regex.sub(r'[^\p{L}0-9\s\n|\-\(\)\#:,\.\?!;\"\'_%*]', '', text)


def chunk_text(text, chunk_len=250):
    chunks = [text[i:i+chunk_len] for i in range(0, len(text), chunk_len)]
    chunks = [c for c in chunks if c.strip() and len(c) > CHUNK_MIN_CHARS]
    return chunks


def overlap_score(hypothesis_chunks, reference_chunks):
    length_modifier = len(hypothesis_chunks) / len(reference_chunks)
    search_distance = max(len(reference_chunks) // 5, 10)
    chunk_scores = []
    chunk_weights = []
    for i, hyp_chunk in enumerate(hypothesis_chunks):
        total_score = 0
        total_len = 0
        chunk_weight = 1
        i_offset = int(i * length_modifier)
        chunk_range = range(max(0, i_offset-search_distance), min(len(reference_chunks), i_offset+search_distance))
        for j in chunk_range:
            ref_chunk = reference_chunks[j]
            score = fuzz.ratio(hyp_chunk, ref_chunk, score_cutoff=40) / 100
            if score > 0:
                total_score += score
                total_len += len(ref_chunk)
        if total_len > 0:
            chunk_weight = math.sqrt(total_len)
        if total_score > 1:
            total_score = 1
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