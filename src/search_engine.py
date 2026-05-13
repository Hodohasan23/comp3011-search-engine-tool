from src.html_parser import tokenize
from src.inverted_index import InvertedIndex
from src.query_processor import QueryProcessor
from src.ranker import Ranker, create_ranker


class SearchEngine:
    def __init__(self, index: InvertedIndex, ranking_method: str = "bm25") -> None:
        self.index = index
        self.query_processor = QueryProcessor()
        self.ranker: Ranker = create_ranker(index, ranking_method)

    def find(self, query: str) -> list[tuple[str, float]]:
        if self.query_processor.is_phrase_query(query):
            return self.find_phrase(query)

        query_terms = tokenize(query)

        if not query_terms:
            return []

        matching_urls: set[str] | None = None

        for term in query_terms:
            urls = set(self.index.postings_for(term).keys())

            if matching_urls is None:
                matching_urls = urls
            else:
                matching_urls = matching_urls.intersection(urls)

        if not matching_urls:
            return []

        results = [
            (url, self.ranker.score(query_terms, url))
            for url in matching_urls
        ]

        return sorted(results, key=lambda item: (-item[1], item[0]))

    def find_phrase(self, query: str) -> list[tuple[str, float]]:
        phrase_terms = self.query_processor.extract_phrase_terms(query)

        if not phrase_terms:
            return []

        candidate_urls: set[str] | None = None

        for term in phrase_terms:
            urls = set(self.index.postings_for(term).keys())

            if candidate_urls is None:
                candidate_urls = urls
            else:
                candidate_urls = candidate_urls.intersection(urls)

        if not candidate_urls:
            return []

        matched_urls = []

        for url in candidate_urls:
            first_term_positions = self.index.postings_for(
                phrase_terms[0]
            )[url].positions

            for start_position in first_term_positions:
                phrase_matches = True

                for offset, term in enumerate(phrase_terms[1:], start=1):
                    positions = self.index.postings_for(term)[url].positions

                    if start_position + offset not in positions:
                        phrase_matches = False
                        break

                if phrase_matches:
                    matched_urls.append(url)
                    break

        results = [
            (url, self.ranker.score(phrase_terms, url))
            for url in matched_urls
        ]

        return sorted(results, key=lambda item: (-item[1], item[0]))

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
