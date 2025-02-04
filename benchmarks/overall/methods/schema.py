from typing import TypedDict, List


class BenchmarkResult(TypedDict):
    markdown: str | List[str]
    time: float | None