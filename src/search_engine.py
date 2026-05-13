import re

from src.html_parser import tokenize
from src.inverted_index import InvertedIndex
from src.query_processor import QueryProcessor
from src.ranker import Ranker, create_ranker


PHRASE_PATTERN = re.compile(r'"([^"]*)"')


class SearchEngine:
    def __init__(self, index: InvertedIndex, ranking_method: str = "bm25") -> None:
        self.index = index
        self.query_processor = QueryProcessor()
        self.ranker: Ranker = create_ranker(index, ranking_method)

    def find(self, query: str) -> list[tuple[str, float]]:
        phrases, free_terms = self.parse_query(query)

        if not phrases and not free_terms:
            return []

        candidate_urls: set[str] | None = None

        for term in free_terms:
            urls = set(self.index.postings_for(term).keys())

            if not urls:
                return []

            if candidate_urls is None:
                candidate_urls = urls
            else:
                candidate_urls &= urls

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

        scoring_terms = list(free_terms)

        for phrase in phrases:
            scoring_terms.extend(phrase)

        results = [
            (url, self.ranker.score(scoring_terms, url))
            for url in candidate_urls
        ]

        return sorted(results, key=lambda item: (-item[1], item[0]))

    def parse_query(self, query: str) -> tuple[list[list[str]], list[str]]:
        phrases: list[list[str]] = []

        def extract_phrase(match: re.Match[str]) -> str:
            phrase_tokens = tokenize(match.group(1))

            if phrase_tokens:
                phrases.append(phrase_tokens)

            return " "

        remaining_query = PHRASE_PATTERN.sub(extract_phrase, query)
        free_terms = tokenize(remaining_query)

        return phrases, free_terms

    def urls_containing_phrase(self, phrase_terms: list[str]) -> set[str]:
        if not phrase_terms:
            return set()

        if len(phrase_terms) == 1:
            return set(self.index.postings_for(phrase_terms[0]).keys())

        postings_per_term = [
            self.index.postings_for(term)
            for term in phrase_terms
        ]

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
                shifted_position_sets.append(
                    {position - offset for position in positions}
                )

            if set.intersection(*shifted_position_sets):
                matching_urls.add(url)

        return matching_urls

    def suggest_terms(self, query: str) -> dict[str, str]:
        query_terms = self.query_processor.clean_query(query)
        vocabulary = set(self.index.terms.keys())

        suggestions = {}

        for term in query_terms:
            suggestion = self.query_processor.suggest_term(term, vocabulary)

            if suggestion is not None:
                suggestions[term] = suggestion

        return suggestions

    def snippet(self, url: str, query_terms: list[str], window: int = 6) -> str:
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
        postings = self.index.postings_for(term)

        return {
            url: {
                "tf": posting.tf,
                "positions": posting.positions,
            }
            for url, posting in postings.items()
        }
