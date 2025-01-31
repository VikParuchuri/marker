from typing import TypedDict, List, Dict, Optional


class BlockScores(TypedDict):
    scores: List[float]
    order_score: float
    overall_score: float
    time: Optional[float]
    markdown: str


class FullResult(TypedDict):
    raw_scores: Dict[int, BlockScores]
    averages_by_type: Dict[str, List[float]]
    averages_by_block_type: Dict[str, List[float]]
    average_time: float
    average_score: float
