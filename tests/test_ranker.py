import pytest

from src.indexer import InvertedIndex
from src.search import BM25Ranker, TFIDFRanker, create_ranker


def test_average_document_length():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    index.add_document("page2", "<p>good books again</p>")

    ranker = BM25Ranker(index)

    assert ranker.average_document_length() == 2.5


def test_score_returns_positive_for_matching_document():
    index = InvertedIndex()
    index.add_document("page1", "<p>rare rare word</p>")
    index.add_document("page2", "<p>common text here</p>")

    ranker = BM25Ranker(index)

    assert ranker.score(["rare"], "page1") > 0


def test_score_returns_zero_for_non_matching_document():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")

    ranker = BM25Ranker(index)

    assert ranker.score(["missing"], "page1") == 0.0


def test_tfidf_score_returns_positive_for_matching_document():
    index = InvertedIndex()
    index.add_document("page1", "<p>rare rare word</p>")
    index.add_document("page2", "<p>common text here</p>")

    ranker = TFIDFRanker(index)

    assert ranker.score(["rare"], "page1") > 0


def test_tfidf_score_returns_zero_for_non_matching_document():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")

    ranker = TFIDFRanker(index)

    assert ranker.score(["missing"], "page1") == 0.0


def test_create_ranker_returns_bm25_by_default():
    index = InvertedIndex()

    ranker = create_ranker(index)

    assert isinstance(ranker, BM25Ranker)


def test_create_ranker_returns_tfidf():
    index = InvertedIndex()

    ranker = create_ranker(index, "tfidf")

    assert isinstance(ranker, TFIDFRanker)


def test_create_ranker_rejects_unknown_method():
    index = InvertedIndex()

    with pytest.raises(ValueError):
        create_ranker(index, "unknown")
