from src.indexer import InvertedIndex
import json

import pytest

from src.indexer import INDEX_SCHEMA_VERSION


def test_add_document_indexes_terms():
    index = InvertedIndex()
    index.add_document("page1", "<p>Good friends good books</p>")

    postings = index.postings_for("good")

    assert "page1" in postings
    assert postings["page1"].tf == 2
    assert postings["page1"].positions == [0, 2]


def test_document_frequency_counts_documents():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    index.add_document("page2", "<p>good books</p>")

    assert index.document_frequency("good") == 2
    assert index.document_frequency("friends") == 1


def test_terms_are_case_insensitive():
    index = InvertedIndex()
    index.add_document("page1", "<p>Good GOOD good</p>")

    assert index.postings_for("GOOD")["page1"].tf == 3


def test_save_and_load_round_trip(tmp_path):
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")

    path = tmp_path / "index.json"
    index.save(str(path))

    loaded = InvertedIndex.load(str(path))

    assert loaded.postings_for("good")["page1"].tf == 1
    assert loaded.doc_lengths["page1"] == 2

def test_saved_index_includes_schema_version(tmp_path):
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")

    path = tmp_path / "index.json"
    index.save(str(path))

    with open(path, encoding="utf-8") as file:
        data = json.load(file)

    assert data["version"] == INDEX_SCHEMA_VERSION


def test_load_rejects_unsupported_schema_version(tmp_path):
    path = tmp_path / "index.json"

    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            {
                "version": 999,
                "terms": {},
                "doc_lengths": {},
            },
            file,
        )

    with pytest.raises(ValueError):
        InvertedIndex.load(str(path))
