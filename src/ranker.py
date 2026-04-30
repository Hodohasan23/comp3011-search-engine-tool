import math

from src.inverted_index import InvertedIndex


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
