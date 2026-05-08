import math
from typing import Protocol

from src.inverted_index import InvertedIndex


class Ranker(Protocol):
    def score(self, query_terms: list[str], url: str) -> float:
        """Return a relevance score for a URL."""
        ...


class BM25Ranker:
    def __init__(self, index: InvertedIndex, k1: float = 1.5, b: float = 0.75) -> None:
        self.index = index
        self.k1 = k1
        self.b = b

    def average_document_length(self) -> float:
        if not self.index.doc_lengths:
            return 0.0

        return sum(self.index.doc_lengths.values()) / len(self.index.doc_lengths)

    def score(self, query_terms: list[str], url: str) -> float:
        score = 0.0
        total_docs = len(self.index.doc_lengths)
        avg_doc_length = self.average_document_length()

        if total_docs == 0 or avg_doc_length == 0:
            return 0.0

        doc_length = self.index.doc_lengths[url]

        for term in query_terms:
            postings = self.index.postings_for(term)

            if url not in postings:
                continue

            tf = postings[url].tf
            df = self.index.document_frequency(term)

            idf = math.log(1 + ((total_docs - df + 0.5) / (df + 0.5)))

            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (
                1 - self.b + self.b * (doc_length / avg_doc_length)
            )

            score += idf * (numerator / denominator)

        return score


class TFIDFRanker:
    def __init__(self, index: InvertedIndex) -> None:
        self.index = index

    def score(self, query_terms: list[str], url: str) -> float:
        score = 0.0
        total_docs = len(self.index.doc_lengths)

        if total_docs == 0:
            return 0.0

        for term in query_terms:
            postings = self.index.postings_for(term)

            if url not in postings:
                continue

            tf = postings[url].tf
            df = self.index.document_frequency(term)

            sublinear_tf = 1 + math.log(tf)
            smoothed_idf = math.log((total_docs + 1) / (df + 1)) + 1

            score += sublinear_tf * smoothed_idf

        return score


def create_ranker(index: InvertedIndex, ranking_method: str = "bm25") -> Ranker:
    method = ranking_method.lower()

    if method == "bm25":
        return BM25Ranker(index)

    if method == "tfidf":
        return TFIDFRanker(index)

    raise ValueError(f"Unknown ranking method: {ranking_method}")
