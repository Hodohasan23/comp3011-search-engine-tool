import math
import re
from typing import Protocol

from src.indexer import InvertedIndex, tokenize


# Matches quoted phrase queries such as "good friends".
PHRASE_PATTERN = re.compile(r'"([^"]*)"')


class QueryProcessor:
    """Handles query cleaning and spelling suggestions."""

    def clean_query(self, query: str) -> list[str]:
        """Tokenise a raw query using the same rules as the index."""
        return tokenize(query)

    def is_phrase_query(self, query: str) -> bool:
        """Return True when the whole query is wrapped in quotes."""
        query = query.strip()

        return len(query) >= 2 and query.startswith('"') and query.endswith('"')

    def extract_phrase_terms(self, query: str) -> list[str]:
        """Extract tokens from a quote-wrapped phrase query."""
        return tokenize(query.strip().strip('"'))

    def levenshtein_distance(self, first: str, second: str) -> int:
        """Compute edit distance between two strings."""
        if first == second:
            return 0

        if not first:
            return len(second)

        if not second:
            return len(first)

        # Dynamic programming row for transforming first -> second.
        previous_row = list(range(len(second) + 1))

        for i, first_char in enumerate(first, start=1):
            current_row = [i]

            for j, second_char in enumerate(second, start=1):
                insert_cost = current_row[j - 1] + 1
                delete_cost = previous_row[j] + 1
                substitute_cost = previous_row[j - 1]

                if first_char != second_char:
                    substitute_cost += 1

                current_row.append(
                    min(insert_cost, delete_cost, substitute_cost)
                )

            previous_row = current_row

        return previous_row[-1]

    def suggest_term(
        self,
        term: str,
        vocabulary: set[str],
        max_distance: int = 2,
    ) -> str | None:
        """Return the closest vocabulary term within max_distance."""
        if term in vocabulary:
            return None

        candidates: list[tuple[int, str]] = []

        for vocab_term in vocabulary:
            # Terms with very different lengths cannot be close matches.
            if abs(len(vocab_term) - len(term)) > max_distance:
                continue

            distance = self.levenshtein_distance(term, vocab_term)

            if distance <= max_distance:
                candidates.append((distance, vocab_term))

        if not candidates:
            return None

        # Prefer closest edit distance, then deterministic alphabetic order.
        candidates.sort(key=lambda item: (item[0], item[1]))

        return candidates[0][1]


class Ranker(Protocol):
    """Shared scoring interface for ranking models."""

    def score(self, query_terms: list[str], url: str) -> float:
        """Return a relevance score for a URL."""
        ...


class BM25Ranker:
    """Okapi BM25 ranking with document-length normalisation."""

    def __init__(self, index: InvertedIndex, k1: float = 1.5, b: float = 0.75) -> None:
        self.index = index
        self.k1 = k1
        self.b = b

    def average_document_length(self) -> float:
        """Return the average indexed document length."""
        if not self.index.doc_lengths:
            return 0.0

        return sum(self.index.doc_lengths.values()) / len(self.index.doc_lengths)

    def score(self, query_terms: list[str], url: str) -> float:
        """Score one URL for a query using BM25."""
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

            # Smoothed BM25 inverse document frequency.
            idf = math.log(1 + ((total_docs - df + 0.5) / (df + 0.5)))

            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (
                1 - self.b + self.b * (doc_length / avg_doc_length)
            )

            score += idf * (numerator / denominator)

        return score


class TFIDFRanker:
    """TF-IDF ranking with sub-linear term frequency."""

    def __init__(self, index: InvertedIndex) -> None:
        self.index = index

    def score(self, query_terms: list[str], url: str) -> float:
        """Score one URL for a query using TF-IDF."""
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

            # Log-scaled TF avoids over-rewarding repeated terms.
            sublinear_tf = 1 + math.log(tf)

            # Smoothed IDF avoids division by zero and keeps scores finite.
            smoothed_idf = math.log((total_docs + 1) / (df + 1)) + 1

            score += sublinear_tf * smoothed_idf

        return score


def create_ranker(index: InvertedIndex, ranking_method: str = "bm25") -> Ranker:
    """Create the selected ranking model."""
    method = ranking_method.lower()

    if method == "bm25":
        return BM25Ranker(index)

    if method == "tfidf":
        return TFIDFRanker(index)

    raise ValueError(f"Unknown ranking method: {ranking_method}")


class SearchEngine:
    """Read-only search layer over the inverted index."""

    def __init__(self, index: InvertedIndex, ranking_method: str = "bm25") -> None:
        self.index = index
        self.query_processor = QueryProcessor()

        # Ranker is swappable, so retrieval and ranking stay separate.
        self.ranker: Ranker = create_ranker(index, ranking_method)

    def find(self, query: str) -> list[tuple[str, float]]:
        """Return ranked URLs matching a query."""
        phrases, free_terms = self.parse_query(query)

        if not phrases and not free_terms:
            return []

        candidate_urls: set[str] | None = None

        # Normal query terms use Boolean AND semantics.
        for term in free_terms:
            urls = set(self.index.postings_for(term).keys())

            if not urls:
                return []

            if candidate_urls is None:
                candidate_urls = urls
            else:
                candidate_urls &= urls

        # Quoted phrases are handled using positional postings.
        for phrase_terms in phrases:
            phrase_urls = self.urls_containing_phrase(phrase_terms)

            if candidate_urls is None:
                candidate_urls = phrase_urls
            else:
                candidate_urls &= phrase_urls

            if not candidate_urls:
                return []

        if not candidate_urls:
            return []

        # Phrase terms also contribute to the final ranking score.
        scoring_terms = list(free_terms)

        for phrase in phrases:
            scoring_terms.extend(phrase)

        results = [
            (url, self.ranker.score(scoring_terms, url))
            for url in candidate_urls
        ]

        return sorted(results, key=lambda item: (-item[1], item[0]))

    def parse_query(self, query: str) -> tuple[list[list[str]], list[str]]:
        """Split a raw query into phrase terms and free terms."""
        phrases: list[list[str]] = []

        def extract_phrase(match: re.Match[str]) -> str:
            phrase_tokens = tokenize(match.group(1))

            if phrase_tokens:
                phrases.append(phrase_tokens)

            # Replace phrase text with a blank so free terms exclude it.
            return " "

        remaining_query = PHRASE_PATTERN.sub(extract_phrase, query)
        free_terms = tokenize(remaining_query)

        return phrases, free_terms

    def urls_containing_phrase(self, phrase_terms: list[str]) -> set[str]:
        """Return URLs where phrase terms appear consecutively."""
        if not phrase_terms:
            return set()

        if len(phrase_terms) == 1:
            return set(self.index.postings_for(phrase_terms[0]).keys())

        postings_per_term = [
            self.index.postings_for(term)
            for term in phrase_terms
        ]

        # If any phrase token is missing, no document can match.
        if any(not postings for postings in postings_per_term):
            return set()

        candidate_urls = set(postings_per_term[0].keys())

        for postings in postings_per_term[1:]:
            candidate_urls &= set(postings.keys())

        matching_urls = set()

        for url in candidate_urls:
            shifted_position_sets = []

            for offset, postings in enumerate(postings_per_term):
                positions = postings[url].positions

                # Shift positions by phrase offset. Consecutive tokens
                # share at least one shifted position.
                shifted_position_sets.append(
                    {position - offset for position in positions}
                )

            if set.intersection(*shifted_position_sets):
                matching_urls.add(url)

        return matching_urls

    def suggest_terms(self, query: str) -> dict[str, str]:
        """Suggest close vocabulary matches for failed query terms."""
        query_terms = self.query_processor.clean_query(query)
        vocabulary = set(self.index.terms.keys())

        suggestions = {}

        for term in query_terms:
            suggestion = self.query_processor.suggest_term(term, vocabulary)

            if suggestion is not None:
                suggestions[term] = suggestion

        return suggestions

    def snippet(self, url: str, query_terms: list[str], window: int = 6) -> str:
        """Return a short token window around the first query match."""
        tokens = self.index.doc_tokens.get(url, [])

        if not tokens:
            return ""

        query_set = set(query_terms)
        match_position = 0

        for position, token in enumerate(tokens):
            if token in query_set:
                match_position = position
                break

        start = max(0, match_position - window)
        end = min(len(tokens), match_position + window + 1)

        snippet_tokens = tokens[start:end]
        snippet_text = " ".join(snippet_tokens)

        if start > 0:
            snippet_text = "... " + snippet_text

        if end < len(tokens):
            snippet_text = snippet_text + " ..."

        return snippet_text

    def print_term(self, term: str) -> dict:
        """Return the posting list for one term."""
        postings = self.index.postings_for(term)

        return {
            url: {
                "tf": posting.tf,
                "positions": posting.positions,
            }
            for url, posting in postings.items()
        }

    