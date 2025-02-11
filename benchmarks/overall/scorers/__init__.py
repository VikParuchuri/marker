from typing import List

from benchmarks.overall.scorers.schema import BlockScores


class BaseScorer:
    def __init__(self):
        pass

    def __call__(self, sample, gt_markdown: List[str], method_markdown: str) -> BlockScores:
        raise NotImplementedError()