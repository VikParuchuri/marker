from thefuzz import fuzz
import re

CHUNK_SIZE = 256
CHUNK_OVERLAP = 128


def tokenize(text):
    # Combined pattern
    pattern = r'([^\w\s\d\'])|([\w\']+)|(\d+)|(\n+)|( +)'
    result = re.findall(pattern, text)
    # Flatten the result and filter out empty strings
    flattened_result = [item for sublist in result for item in sublist if item]
    return flattened_result


def chunk_text(text, overlap=False):
    tokens = tokenize(text)
    chunks = []
    step = CHUNK_SIZE
    if overlap:
        step -= CHUNK_OVERLAP
    for i in range(0, len(tokens), step):
        chunks.append(''.join(tokens[i:i+CHUNK_SIZE]))
    return chunks


def overlap_score(hypothesis_chunks, reference_chunks):
    length_modifier = len(hypothesis_chunks) / len(reference_chunks)
    search_distance = max(len(reference_chunks) // 5, 10)
    chunk_scores = []
    for i, hyp_chunk in enumerate(hypothesis_chunks):
        max_score = 0
        i_offset = int(i * length_modifier)
        chunk_range = range(max(0, i_offset-search_distance), min(len(reference_chunks), i_offset+search_distance))
        for j in chunk_range:
            ref_chunk = reference_chunks[j]
            score = fuzz.ratio(hyp_chunk, ref_chunk)
            if score > max_score:
                max_score = score
        chunk_scores.append(max_score)
    return chunk_scores


def score_text(hypothesis, reference):
    # Returns a 0-1 alignment score
    hypothesis_chunks = chunk_text(hypothesis)
    reference_chunks = chunk_text(reference)
    chunk_scores = overlap_score(hypothesis_chunks, reference_chunks)
    return sum(chunk_scores) / len(chunk_scores) / 100