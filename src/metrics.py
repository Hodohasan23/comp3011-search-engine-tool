from pathlib import Path
from time import perf_counter

from src.inverted_index import InvertedIndex


class Timer:
    def __init__(self) -> None:
        self.start_time: float | None = None
        self.end_time: float | None = None

    def start(self) -> None:
        self.start_time = perf_counter()

    def stop(self) -> None:
        self.end_time = perf_counter()

    def elapsed(self) -> float:
        if self.start_time is None or self.end_time is None:
            return 0.0

        return self.end_time - self.start_time


def index_summary(index: InvertedIndex, index_path: str | None = None) -> dict:
    summary = {
        "documents": len(index.doc_lengths),
        "vocabulary_size": len(index.terms),
        "total_tokens": sum(index.doc_lengths.values()),
    }

    if index_path is not None and Path(index_path).exists():
        summary["index_size_bytes"] = Path(index_path).stat().st_size

    return summary
