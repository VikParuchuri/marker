from typing import List

from rapidfuzz import fuzz

from benchmarks.overall.scorers.clean import MarkdownCleaner
from benchmarks.overall.scorers.schema import BlockScores
from benchmarks.overall.scorers import BaseScorer


class HeuristicScorer(BaseScorer):
    def __call__(self, sample, gt_markdown: List[str], method_markdown: str) -> BlockScores:
        if not method_markdown:
            return {
                "score": 0,
                "specific_scores": {
                    "order": 0,
                    "by_block": [0] * len(gt_markdown)
                }
            }

        # Standardize inputs
        gt_markdown = [self.clean_input(block) for block in gt_markdown]
        method_markdown = self.clean_input(method_markdown)

        alignments = self.find_fuzzy_alignments(method_markdown, gt_markdown)
        scores = [alignment["score"] for alignment in alignments]

        # Find order score
        orders = [alignment["start"] for alignment in alignments]
        correct_order = list(range(len(gt_markdown)))
        actual_order = sorted(range(len(gt_markdown)), key=lambda x: orders[x])
        order_score = self.kendall_tau(correct_order, actual_order)

        # Weight score by sequence length
        gt_weights = [len(g) for g in gt_markdown]
        weighted_scores = [score * weight for score, weight in zip(scores, gt_weights)]

        # Weight the score by sequence length
        overall_score = sum(weighted_scores) / max(1, sum(gt_weights))
        overall_score = overall_score * 0.8 + order_score * 0.2
        return {
            "score": overall_score,
            "specific_scores": {
                "order": order_score,
                "by_block": scores
            },
        }

    @staticmethod
    def kendall_tau(correct_order: List[int], actual_order: List[int]) -> float:
        n = len(correct_order)
        concordant = 0
        discordant = 0

        if n <= 1:
            return 100

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

    @staticmethod
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


    @staticmethod
    def clean_input(md: str):
        cleaner = MarkdownCleaner()
        return cleaner(md)