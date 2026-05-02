from src.html_parser import tokenize


class QueryProcessor:
    def clean_query(self, query: str) -> list[str]:
        """Convert a raw query into searchable tokens."""
        return tokenize(query)

    def is_phrase_query(self, query: str) -> bool:
        """Check whether the query is wrapped in quotes."""
        query = query.strip()

        return (
            len(query) >= 2
            and query.startswith('"')
            and query.endswith('"')
        )

    def extract_phrase_terms(self, query: str) -> list[str]:
        """Extract tokens from a quoted phrase query."""
        cleaned = query.strip().strip('"')

        return tokenize(cleaned)
