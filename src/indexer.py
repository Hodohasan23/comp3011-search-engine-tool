import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from bs4 import BeautifulSoup


# Matches lowercase words and digits after text has been normalised.
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

# Explicit schema version prevents old index files being loaded silently
# after the JSON structure changes.
INDEX_SCHEMA_VERSION = 1

# Small curated stop-word list used to reduce noise in the index.
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
    "can", "could", "did", "do", "does", "for", "from", "had", "has",
    "have", "he", "her", "hers", "him", "his", "i", "if", "in", "into",
    "is", "it", "its", "me", "my", "of", "on", "or", "our", "ours",
    "she", "should", "so", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "to", "was",
    "we", "were", "what", "when", "where", "which", "who", "whom",
    "why", "will", "with", "would", "you", "your", "yours",
}


@dataclass
class Posting:
    """Stores one term's frequency and positions inside one document."""

    tf: int
    positions: list[int]


def extract_visible_text(html: str) -> str:
    """Extract searchable text from HTML while removing page chrome."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove elements that do not represent meaningful page content.
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    return soup.get_text(" ", strip=True)


def tokenize(text: str, remove_stopwords: bool = False) -> list[str]:
    """Convert text into lowercase full-word tokens."""
    tokens = TOKEN_PATTERN.findall(text.lower())

    if remove_stopwords:
        return [token for token in tokens if token not in STOPWORDS]

    return tokens


def html_to_tokens(html: str, remove_stopwords: bool = False) -> list[str]:
    """Convert raw HTML into clean tokens used by the index."""
    text = extract_visible_text(html)

    return tokenize(text, remove_stopwords=remove_stopwords)


class InvertedIndex:
    """Builds and stores a positional inverted index."""

    def __init__(self, remove_stopwords: bool = True) -> None:
        self.remove_stopwords = remove_stopwords

        # term -> url -> Posting(tf, positions)
        self.terms: dict[str, dict[str, Posting]] = {}

        # url -> number of indexed tokens
        self.doc_lengths: dict[str, int] = {}

        # url -> token sequence, used later for snippets
        self.doc_tokens: dict[str, list[str]] = {}

    def add_document(self, url: str, html: str) -> None:
        """Tokenise one HTML page and merge it into the index."""
        tokens = html_to_tokens(
            html,
            remove_stopwords=self.remove_stopwords,
        )

        self.doc_lengths[url] = len(tokens)
        self.doc_tokens[url] = tokens

        # Store both term frequency and token positions.
        for position, token in enumerate(tokens):
            if token not in self.terms:
                self.terms[token] = {}

            if url not in self.terms[token]:
                self.terms[token][url] = Posting(tf=0, positions=[])

            self.terms[token][url].tf += 1
            self.terms[token][url].positions.append(position)

    def document_frequency(self, term: str) -> int:
        """Return the number of documents containing a term."""
        return len(self.terms.get(term.lower(), {}))

    def postings_for(self, term: str) -> dict[str, Posting]:
        """Return all postings for a term."""
        return self.terms.get(term.lower(), {})

    def save(self, path: str) -> None:
        """Persist the whole index as versioned JSON."""
        data = {
            "version": INDEX_SCHEMA_VERSION,
            "remove_stopwords": self.remove_stopwords,
            "terms": {
                term: {
                    url: asdict(posting)
                    for url, posting in postings.items()
                }
                for term, postings in self.terms.items()
            },
            "doc_lengths": self.doc_lengths,
            "doc_tokens": self.doc_tokens,
        }

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

    @classmethod
    def load(cls, path: str) -> "InvertedIndex":
        """Load an index from disk and validate the schema version."""
        with open(path, encoding="utf-8") as file:
            data = json.load(file)

        version = data.get("version")

        if version != INDEX_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported index schema version: {version}"
            )

        index = cls(
            remove_stopwords=data.get("remove_stopwords", True)
        )
        index.doc_lengths = data["doc_lengths"]
        index.doc_tokens = data.get("doc_tokens", {})

        # Rehydrate raw dictionaries back into Posting objects.
        index.terms = {
            term: {
                url: Posting(
                    tf=posting["tf"],
                    positions=posting["positions"],
                )
                for url, posting in postings.items()
            }
            for term, postings in data["terms"].items()
        }

        return index