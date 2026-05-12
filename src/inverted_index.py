import json
from dataclasses import asdict, dataclass
from pathlib import Path

from src.html_parser import html_to_tokens


INDEX_SCHEMA_VERSION = 1


@dataclass
class Posting:
    tf: int
    positions: list[int]


class InvertedIndex:
    def __init__(self, remove_stopwords: bool = True) -> None:
        self.remove_stopwords = remove_stopwords
        self.terms: dict[str, dict[str, Posting]] = {}
        self.doc_lengths: dict[str, int] = {}

    def add_document(self, url: str, html: str) -> None:
        tokens = html_to_tokens(
            html,
            remove_stopwords=self.remove_stopwords,
        )
        self.doc_lengths[url] = len(tokens)

        for position, token in enumerate(tokens):
            if token not in self.terms:
                self.terms[token] = {}

            if url not in self.terms[token]:
                self.terms[token][url] = Posting(tf=0, positions=[])

            self.terms[token][url].tf += 1
            self.terms[token][url].positions.append(position)

    def document_frequency(self, term: str) -> int:
        return len(self.terms.get(term.lower(), {}))

    def postings_for(self, term: str) -> dict[str, Posting]:
        return self.terms.get(term.lower(), {})

    def save(self, path: str) -> None:
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
        }

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

    @classmethod
    def load(cls, path: str) -> "InvertedIndex":
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
