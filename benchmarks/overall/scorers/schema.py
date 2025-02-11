from typing import TypedDict, List, Optional, Dict


class BlockScores(TypedDict):
    score: float
    specific_scores: Dict[str, float | List[float]]
